"""State persistence and date filtering for incremental job fetching."""

import json
from datetime import date, datetime, time, timezone
from pathlib import Path

import pandas as pd


DEFAULT_STATE_FILE = Path(".pipeline_state.json")
DEFAULT_RESULTS_WANTED = 15
MAX_AUTO_RESULTS_WANTED = 100


def _state_key(search_term: str, location: str) -> str:
    return json.dumps(
        [search_term.strip().casefold(), location.strip().casefold()],
        ensure_ascii=False,
    )


def load_last_fetch_timestamp(
    search_term: str,
    location: str,
    state_file: str | Path = DEFAULT_STATE_FILE,
) -> datetime | None:
    """Load the timestamp for a search/location pair, if available."""
    try:
        with Path(state_file).open(encoding="utf-8") as file:
            state = json.load(file)
        timestamp = state["last_fetch_timestamps"][_state_key(search_term, location)]
        loaded_timestamp = datetime.fromisoformat(timestamp)
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None

    if loaded_timestamp.tzinfo is None:
        return None

    return loaded_timestamp.astimezone(timezone.utc)


def save_last_fetch_timestamp(
    timestamp: datetime,
    search_term: str,
    location: str,
    state_file: str | Path = DEFAULT_STATE_FILE,
) -> None:
    """Save a UTC timestamp for a search/location pair."""
    if timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")

    state_path = Path(state_file)
    try:
        with state_path.open(encoding="utf-8") as file:
            state = json.load(file)
    except FileNotFoundError:
        state = {}
    except json.JSONDecodeError:
        state = {}

    if not isinstance(state, dict):
        state = {}
    timestamps = state.get("last_fetch_timestamps", {})
    if not isinstance(timestamps, dict):
        timestamps = {}
    timestamps[_state_key(search_term, location)] = timestamp.astimezone(
        timezone.utc
    ).isoformat()

    with Path(state_file).open("w", encoding="utf-8") as file:
        json.dump({"last_fetch_timestamps": timestamps}, file)


def parse_start_date(value: str) -> datetime:
    """Parse a YYYY-MM-DD CLI value as the start of that UTC day."""
    return datetime.combine(date.fromisoformat(value), time.min, tzinfo=timezone.utc)


def start_of_utc_day(timestamp: datetime) -> datetime:
    """Round a timezone-aware timestamp down to the start of its UTC day."""
    if timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")

    return datetime.combine(
        timestamp.astimezone(timezone.utc).date(), time.min, tzinfo=timezone.utc
    )


def resolve_results_wanted(
    explicit_count: int | None,
    last_fetch_timestamp: datetime | None,
    now: datetime | None = None,
) -> int:
    """Resolve an explicit count or an adaptive catch-up fetch limit."""
    if explicit_count is not None:
        return explicit_count
    if last_fetch_timestamp is None:
        return DEFAULT_RESULTS_WANTED
    if last_fetch_timestamp.tzinfo is None:
        raise ValueError("last_fetch_timestamp must be timezone-aware")

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    elapsed_days = max(
        1,
        (
            current_time.astimezone(timezone.utc).date()
            - last_fetch_timestamp.astimezone(timezone.utc).date()
        ).days,
    )
    return min(DEFAULT_RESULTS_WANTED * elapsed_days, MAX_AUTO_RESULTS_WANTED)


def filter_jobs_by_start_date(
    jobs: pd.DataFrame, start_date: datetime | None
) -> pd.DataFrame:
    """Return ads posted or updated on/after the target timestamp."""
    if start_date is None:
        return jobs
    if start_date.tzinfo is None:
        raise ValueError("start_date must be timezone-aware")

    date_columns = [
        column for column in ("date_posted", "date_updated") if column in jobs.columns
    ]
    if not date_columns:
        return jobs.iloc[0:0].copy()

    matching_dates = pd.Series(False, index=jobs.index)
    target_timestamp = pd.Timestamp(start_date)
    for column in date_columns:
        ad_dates = pd.to_datetime(jobs[column], errors="coerce", utc=True)
        matching_dates |= ad_dates >= target_timestamp

    return jobs.loc[matching_dates].copy()
