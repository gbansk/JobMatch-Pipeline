import hashlib
import re
import sqlite3
from datetime import datetime, timedelta

DB_NAME = "jobs.db"


def init_db():
    """Creates the job tracking table if it doesn't already exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS job_listings (
            job_id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            company TEXT NOT NULL,
            title TEXT NOT NULL,
            location TEXT,
            canonical_hash TEXT NOT NULL,
            raw_url TEXT NOT NULL,
            match_score REAL,
            verdict TEXT,
            summary TEXT,
            status TEXT DEFAULT 'NEW',
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    conn.commit()
    conn.close()


def generate_canonical_hash(company: str, title: str) -> str:
    """Creates a normalized hash from company name and job title."""
    clean_company = re.sub(r"[^a-z0-9]", "", str(company).lower())
    clean_title = re.sub(r"[^a-z0-9]", "", str(title).lower())

    # Strip common seniority words that vary across duplicate postings
    clean_title = clean_title.replace("senior", "sr").replace("lead", "sr")

    combined = f"{clean_company}:{clean_title}"
    return hashlib.md5(combined.encode("utf-8")).hexdigest()


def is_duplicate(
    job_id: str, company: str, title: str, days_lookback: int = 30
) -> bool:
    """Checks if a job has already been recorded by Job ID or by Canonical Hash within N days."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Exact Job ID check
    cursor.execute("SELECT 1 FROM job_listings WHERE job_id = ?", (job_id,))
    if cursor.fetchone():
        conn.close()
        return True

    # 2. Canonical Title + Company Hash within lookback window
    cutoff_date = (datetime.now() - timedelta(days=days_lookback)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    canonical_hash = generate_canonical_hash(company, title)

    cursor.execute(
        """
        SELECT 1 FROM job_listings 
        WHERE canonical_hash = ? AND first_seen_at >= ?
    """,
        (canonical_hash, cutoff_date),
    )

    result = cursor.fetchone()
    conn.close()
    return result is not None


def save_job(
    job_id: str,
    platform: str,
    company: str,
    title: str,
    location: str,
    raw_url: str,
    score: float = None,
    verdict: str = None,
    summary: str = None,
):
    """Inserts a new job record into the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    canonical_hash = generate_canonical_hash(company, title)

    cursor.execute(
        """
        INSERT OR REPLACE INTO job_listings 
        (job_id, platform, company, title, location, canonical_hash, raw_url, match_score, verdict, summary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            job_id,
            platform,
            company,
            title,
            location,
            canonical_hash,
            raw_url,
            score,
            verdict,
            summary,
        ),
    )

    conn.commit()
    conn.close()


def get_unprocessed_jobs() -> list[dict]:
    """Fetches all jobs from job_listings that have not yet been evaluated."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Enables dictionary-style column access
    cursor = conn.cursor()

    # Query job_listings table where verdict is missing or set to pending
    cursor.execute(
        """
        SELECT job_id AS id, company, title, location, raw_url, summary AS description 
        FROM job_listings 
        WHERE verdict IS NULL OR verdict = 'pending'
    """
    )
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def update_job_status(job_id: str, status: str, score: float = None):
    """Updates evaluation verdict and match_score for a job record in job_listings."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE job_listings 
        SET verdict = ?, match_score = ? 
        WHERE job_id = ?
    """,
        (status, score, job_id),
    )

    conn.commit()
    conn.close()
