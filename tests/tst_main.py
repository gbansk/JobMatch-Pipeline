import json
import os
import sys
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

import main

# --- Fixtures ---

@pytest.fixture
def sample_profile_dir(tmp_path):
    """Creates a temporary profiles directory with two mock profile JSON files."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()

    dev_profile = profiles_dir / "developer.json"
    dev_profile.write_text(json.dumps({"basics": {"name": "Alice"}, "skills": ["Go", "Python"]}), encoding="utf-8")

    lead_profile = profiles_dir / "lead.json"
    lead_profile.write_text(json.dumps({"basics": {"name": "Alice"}, "skills": ["Management"]}), encoding="utf-8")

    return str(profiles_dir)


# --- Tests for load_profiles ---

def test_load_profiles_success(sample_profile_dir):
    profiles = main.load_profiles(sample_profile_dir)
    assert len(profiles) == 2
    tracks = {p["track"] for p in profiles}
    assert tracks == {"Developer CV", "Lead CV"}


def test_load_profiles_empty_dir(tmp_path):
    empty_dir = tmp_path / "empty_profiles"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError, match="No profile JSON files found"):
        main.load_profiles(str(empty_dir))


def test_load_profiles_ignores_template(tmp_path):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()

    # Create valid profile
    dev_profile = profiles_dir / "developer.json"
    dev_profile.write_text(json.dumps({"basics": {"name": "Alice"}}), encoding="utf-8")

    # Create template file that should be ignored
    template_file = profiles_dir / "template.json"
    template_file.write_text(json.dumps({"basics": {"name": "TEMPLATE"}}), encoding="utf-8")

    profiles = main.load_profiles(str(profiles_dir))

    # Assert only developer.json was loaded
    assert len(profiles) == 1
    assert profiles[0]["track"] == "Developer CV"


# --- Tests for run_linkedin_scraper ---

@patch("main.JOBSPY_AVAILABLE", False)
def test_run_linkedin_scraper_jobspy_missing():
    with pytest.raises(SystemExit) as exc_info:
        main.run_linkedin_scraper("Engineer", "Melbourne")
    assert exc_info.value.code == 1


@patch("main.scrape_jobs")
@patch("main.is_duplicate")
@patch("main.save_job")
def test_run_linkedin_scraper_success(mock_save, mock_is_dup, mock_scrape):
    # Mock scraper returning two jobs: one new, one duplicate
    mock_df = pd.DataFrame([
        {"id": "job-1", "company": "Co A", "title": "Dev 1", "location": "Melb", "job_url": "http://ex1.com", "description": "Desc 1"},
        {"id": "job-2", "company": "Co B", "title": "Dev 2", "location": "Syd", "job_url": "http://ex2.com", "description": "Desc 2"},
    ])
    mock_scrape.return_value = mock_df
    mock_is_dup.side_effect = [False, True]  # job-1 is new, job-2 is duplicate

    count = main.run_linkedin_scraper("Software", "Australia", results_wanted=5)

    assert count == 1
    mock_save.assert_called_once_with(
        job_id="job-1",
        platform="linkedin",
        company="Co A",
        title="Dev 1",
        location="Melb",
        raw_url="http://ex1.com",
        summary="Desc 1"
    )


@patch("main.scrape_jobs")
def test_run_linkedin_scraper_empty_dataframe(mock_scrape):
    mock_scrape.return_value = pd.DataFrame()
    count = main.run_linkedin_scraper("Software", "Australia")
    assert count == 0


@patch("main.scrape_jobs")
def test_run_linkedin_scraper_exception_handling(mock_scrape):
    mock_scrape.side_effect = Exception("API rate limit exceeded")
    count = main.run_linkedin_scraper("Software", "Australia")
    assert count == 0


# --- Tests for generate_html_report ---

def test_generate_html_report_creation(tmp_path):
    report_file = tmp_path / "output" / "report.html"
    evaluated_jobs = [
        {
            "company": "Tech Corp",
            "title": "Senior Engineer",
            "location": "Melbourne",
            "score": 85,
            "status": "matched",
            "raw_url": "https://example.com/job",
            "cv_track": "Developer CV",
            "pdf_path": str(tmp_path / "output" / "CoverLetter.pdf")
        },
        {
            "company": "Low Fit Inc",
            "title": "Junior QA",
            "location": "Remote",
            "score": 45,
            "status": "skipped_low_score",
            "raw_url": "#",
            "cv_track": "Developer CV",
            "pdf_path": "#"
        }
    ]

    main.generate_html_report(evaluated_jobs, str(report_file))

    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")
    assert "Tech Corp" in content
    assert "85%" in content
    assert "#28a745" in content  # Green color for high score
    assert "#dc3545" in content  # Red color for low score
    assert "CoverLetter.pdf" in content


# --- Tests for run_pipeline ---

@patch("main.get_unprocessed_jobs")
def test_run_pipeline_no_pending_jobs(mock_get_unprocessed):
    mock_get_unprocessed.return_value = []
    # Should exit early without raising errors
    main.run_pipeline("profiles", "llama3.2", "template.tex", "output")
    mock_get_unprocessed.assert_called_once()


@patch("main.generate_html_report")
@patch("main.update_job_status")
@patch("main.evaluate_job")
@patch("main.get_unprocessed_jobs")
def test_run_pipeline_multi_profile_evaluation(
    mock_get_unprocessed, mock_eval, mock_update, mock_report, sample_profile_dir, tmp_path
):
    mock_get_unprocessed.return_value = [
        {"id": "job-100", "title": "Go Developer", "company": "Acme", "location": "Melb", "raw_url": "http://ex.com", "description": "Go role"}
    ]

    # First track score = 65, second track score = 88
    mock_eval.side_effect = [
        ("Cover letter body 1", 65),
        ("Cover letter body 2", 88),
    ]

    out_dir = str(tmp_path / "output")
    main.run_pipeline(
        profiles_dir=sample_profile_dir,
        model="llama3.2",
        template_path="template.tex",
        output_dir=out_dir,
        min_score=70
    )

    # Should update DB with status='matched' and highest score 88
    mock_update.assert_called_once_with("job-100", status="matched", score=88)
    mock_report.assert_called_once()


@patch("main.generate_html_report")
@patch("main.update_job_status")
@patch("main.evaluate_job")
@patch("main.get_unprocessed_jobs")
def test_run_pipeline_low_score_skipped(
    mock_get_unprocessed, mock_eval, mock_update, mock_report, sample_profile_dir, tmp_path
):
    mock_get_unprocessed.return_value = [
        {"id": "job-200", "title": "Product Owner", "company": "Beta", "location": "Syd", "raw_url": "#", "description": "PO role"}
    ]

    # Scores fall below min_score (70)
    mock_eval.side_effect = [
        ("Body 1", 40),
        ("Body 2", 55),
    ]

    out_dir = str(tmp_path / "output")
    main.run_pipeline(
        profiles_dir=sample_profile_dir,
        model="llama3.2",
        template_path="template.tex",
        output_dir=out_dir,
        min_score=70
    )

    mock_update.assert_called_once_with("job-200", status="skipped_low_score", score=55)


# --- Tests for CLI main() ---

def test_main_missing_profiles_directory(tmp_path):
    test_args = ["main.py", "--profiles", str(tmp_path / "non_existent_dir")]
    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit) as exc_info:
            main.main()
        assert exc_info.value.code == 1


@patch("main.run_pipeline")
@patch("main.run_linkedin_scraper")
@patch("main.init_db")
def test_main_skip_scrape_flag(mock_init, mock_scrape, mock_pipeline, sample_profile_dir):
    test_args = ["main.py", "--profiles", sample_profile_dir, "--skip-scrape"]
    with patch.object(sys, "argv", test_args):
        main.main()

    mock_init.assert_called_once()
    mock_scrape.assert_not_called()
    mock_pipeline.assert_called_once()
