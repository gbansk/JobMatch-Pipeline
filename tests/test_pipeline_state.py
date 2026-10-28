from datetime import datetime, timezone

import pandas as pd
import pytest

from pipeline_state import (
    filter_jobs_by_start_date,
    load_last_fetch_timestamp,
    parse_start_date,
    resolve_results_wanted,
    save_last_fetch_timestamp,
    start_of_utc_day,
)


def test_save_and_load_last_fetch_timestamp(tmp_path):
    state_file = tmp_path / ".pipeline_state.json"
    timestamp = datetime(2026, 10, 1, 12, 30, tzinfo=timezone.utc)

    save_last_fetch_timestamp(timestamp, state_file)

    assert load_last_fetch_timestamp(state_file) == timestamp


def test_load_last_fetch_timestamp_returns_none_when_file_missing(tmp_path):
    assert load_last_fetch_timestamp(tmp_path / ".pipeline_state.json") is None


def test_load_last_fetch_timestamp_returns_none_for_naive_timestamp(tmp_path):
    state_file = tmp_path / ".pipeline_state.json"
    state_file.write_text(
        '{"last_fetch_timestamp": "2026-10-01T12:30:00"}', encoding="utf-8"
    )

    assert load_last_fetch_timestamp(state_file) is None


def test_save_last_fetch_timestamp_rejects_naive_timestamp(tmp_path):
    with pytest.raises(ValueError, match="timezone-aware"):
        save_last_fetch_timestamp(
            datetime(2026, 10, 1, 12, 30), tmp_path / ".pipeline_state.json"
        )


def test_filter_jobs_by_start_date_includes_date_boundary_and_updated_fallback():
    jobs = pd.DataFrame(
        [
            {"id": "before", "date_posted": "2026-09-30T23:59:59Z"},
            {"id": "boundary", "date_posted": "2026-10-01T00:00:00Z"},
            {"id": "after", "date_posted": "2026-10-02T00:00:00Z"},
            {
                "id": "updated",
                "date_posted": None,
                "date_updated": "2026-10-01T10:00:00Z",
            },
            {
                "id": "updated-after-posting",
                "date_posted": "2026-09-30T10:00:00Z",
                "date_updated": "2026-10-01T10:00:00Z",
            },
        ]
    )

    filtered = filter_jobs_by_start_date(jobs, parse_start_date("2026-10-01"))

    assert filtered["id"].tolist() == [
        "boundary",
        "after",
        "updated",
        "updated-after-posting",
    ]


def test_filter_jobs_by_start_date_returns_original_jobs_without_target_date():
    jobs = pd.DataFrame([{"id": "job-1"}])

    assert filter_jobs_by_start_date(jobs, None) is jobs


def test_filter_jobs_by_start_date_rejects_naive_date_and_unknown_date_columns():
    jobs = pd.DataFrame([{"id": "job-1"}])

    with pytest.raises(ValueError, match="timezone-aware"):
        filter_jobs_by_start_date(jobs, datetime(2026, 10, 1))

    filtered = filter_jobs_by_start_date(jobs, parse_start_date("2026-10-01"))

    assert filtered.empty


def test_parse_start_date_rejects_invalid_date():
    with pytest.raises(ValueError):
        parse_start_date("2026-10-32")


def test_start_of_utc_day_uses_utc_date():
    timestamp = datetime.fromisoformat("2026-10-01T01:00:00+10:00")

    assert start_of_utc_day(timestamp) == datetime(2026, 9, 30, tzinfo=timezone.utc)


def test_start_of_utc_day_rejects_naive_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        start_of_utc_day(datetime(2026, 10, 1))


def test_resolve_results_wanted_uses_default_for_first_run_or_explicit_count():
    assert resolve_results_wanted(None, None) == 15
    assert resolve_results_wanted(25, parse_start_date("2026-10-01")) == 25


def test_resolve_results_wanted_scales_by_elapsed_days_and_caps_at_100():
    last_fetch_timestamp = datetime(2026, 10, 1, tzinfo=timezone.utc)

    assert (
        resolve_results_wanted(
            None,
            last_fetch_timestamp,
            now=datetime(2026, 10, 2, tzinfo=timezone.utc),
        )
        == 15
    )
    assert (
        resolve_results_wanted(
            None,
            last_fetch_timestamp,
            now=datetime(2026, 10, 5, tzinfo=timezone.utc),
        )
        == 60
    )
    assert (
        resolve_results_wanted(
            None,
            last_fetch_timestamp,
            now=datetime(2026, 10, 15, tzinfo=timezone.utc),
        )
        == 100
    )


def test_resolve_results_wanted_rejects_naive_last_fetch_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        resolve_results_wanted(None, datetime(2026, 10, 1))
