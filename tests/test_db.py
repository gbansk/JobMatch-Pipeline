import sqlite3
from datetime import datetime, timedelta
import pytest
import db


@pytest.fixture
def mock_db(tmp_path, monkeypatch):
    """Creates a fresh, isolated SQLite database in a temp directory for every test."""
    db_file = tmp_path / "test_jobs.db"
    monkeypatch.setattr(db, "DB_NAME", str(db_file))
    db.init_db()
    return db_file


def test_init_db_creates_table(mock_db):
    """Verifies schema creation."""
    conn = sqlite3.connect(mock_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='job_listings';")
    table = cursor.fetchone()
    conn.close()
    assert table is not None


@pytest.mark.parametrize(
    "company_a, title_a, company_b, title_b",
    [
        ("Acme Corp", "Senior Go Engineer", "ACME Corp.", "Sr Go Engineer"),
        ("Google Inc.", "Lead Software Engineer", "google inc", "Sr Software Engineer"),
        ("Stripe!", "Backend Developer (Remote)", "stripe", "backend developer remote"),
    ],
)
def test_generate_canonical_hash_normalization(company_a, title_a, company_b, title_b):
    """Verifies string cleanup and normalization."""
    hash_a = db.generate_canonical_hash(company_a, title_a)
    hash_b = db.generate_canonical_hash(company_b, title_b)
    assert hash_a == hash_b


def test_is_duplicate_new_job(mock_db):
    """Unseen jobs should not be flagged as duplicates."""
    assert not db.is_duplicate("job-1", "Company X", "Engineer")


def test_is_duplicate_by_exact_id(mock_db):
    """Exact job_id match triggers duplicate detection."""
    db.save_job("job-1", "linkedin", "Company X", "Engineer", "Melb", "http://example.com")
    assert db.is_duplicate("job-1", "Different Company", "Different Title")


def test_is_duplicate_by_canonical_hash_within_window(mock_db):
    """Canonical hash match within lookback window triggers duplicate detection."""
    db.save_job("job-1", "linkedin", "Acme Corp", "Senior Go Developer", "Melb", "http://example.com")
    assert db.is_duplicate("job-2", "ACME Corp.", "Sr Go Developer")


def test_is_duplicate_expired_lookback_window(mock_db):
    """Matches older than days_lookback are not flagged as duplicates."""
    db.save_job("job-old", "seek", "Old Corp", "Developer", "Melb", "http://example.com")

    # Backdate the record in SQLite
    old_date = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(mock_db)
    conn.execute("UPDATE job_listings SET first_seen_at = ? WHERE job_id = 'job-old'", (old_date,))
    conn.commit()
    conn.close()

    # Lookback window = 30 days -> Old record should be ignored
    assert not db.is_duplicate("job-new", "Old Corp", "Developer", days_lookback=30)


def test_get_unprocessed_jobs(mock_db):
    """Only fetches jobs where verdict is NULL or 'pending'."""
    db.save_job("job-1", "linkedin", "Co A", "Dev A", "Loc", "http://ex.com/1", summary="Summary 1")
    db.save_job("job-2", "seek", "Co B", "Dev B", "Loc", "http://ex.com/2", verdict="pending", summary="Summary 2")
    db.save_job("job-3", "seek", "Co C", "Dev C", "Loc", "http://ex.com/3", verdict="matched", summary="Summary 3")

    unprocessed = db.get_unprocessed_jobs()
    assert len(unprocessed) == 2

    job_ids = {j["id"] for j in unprocessed}
    assert job_ids == {"job-1", "job-2"}


def test_update_job_status(mock_db):
    """Verifies updating verdict and match_score."""
    db.save_job("job-1", "linkedin", "Co A", "Dev A", "Loc", "http://ex.com/1")
    db.update_job_status("job-1", "matched", 95.5)

    conn = sqlite3.connect(mock_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT verdict, match_score FROM job_listings WHERE job_id = 'job-1'")
    row = dict(cursor.fetchone())
    conn.close()

    assert row["verdict"] == "matched"
    assert row["match_score"] == 95.5
