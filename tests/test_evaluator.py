import json
import os
import subprocess
from unittest.mock import MagicMock, patch
import pytest

import evaluator

# --- Fixtures ---

@pytest.fixture
def sample_cv():
    return {
        "basics": {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "+1234567890"
        },
        "summary": "Experienced Software Architect.",
        "skills": ["Python", "Golang", "Docker"],
        "experience": [
            {
                "role_header": "Senior Developer at Tech Co",
                "highlights": ["Built distributed systems", "Optimized database queries"]
            }
        ]
    }


@pytest.fixture
def latex_template(tmp_path):
    template_file = tmp_path / "template.tex"
    template_file.write_text(
        "\\documentclass{article}\n\\begin{document}\n"
        "Name: <<NAME>>\nEmail: <<EMAIL>>\nPhone: <<PHONE>>\nBody: <<BODY>>\n"
        "\\end{document}",
        encoding="utf-8"
    )
    return str(template_file)


# --- Tests for strip_ansi_codes ---

def test_strip_ansi_codes_empty():
    assert evaluator.strip_ansi_codes("") == ""
    assert evaluator.strip_ansi_codes(None) == ""


def test_strip_ansi_codes_formatting():
    # Test ANSI codes, terminal cursor artifacts like [6D, and paragraph spacing
    raw = "\x1b[31mHello\x1b[0m world! [6D\n\n  Paragraph   two with   extra spaces.  "
    expected = "Hello world!\n\nParagraph two with extra spaces."
    assert evaluator.strip_ansi_codes(raw) == expected


# --- Tests for build_ollama_prompt ---

def test_build_ollama_prompt_full_data(sample_cv):
    prompt = evaluator.build_ollama_prompt(sample_cv, "Need a Python developer.")

    # Basics and Skills
    assert "Jane Doe" in prompt
    assert "Python, Golang, Docker" in prompt

    # Job Description
    assert "Need a Python developer." in prompt

    # Prompt Instructions & Format
    assert "Candidate Skills: Python, Golang, Docker" in prompt
    assert "fit_score" in prompt
    assert "cover_letter_body" in prompt


def test_build_ollama_prompt_missing_optional_keys():
    sparse_cv = {"basics": {"name": "Alex"}}
    prompt = evaluator.build_ollama_prompt(sparse_cv, "Generic job description.")
    assert "Alex" in prompt
    assert "Candidate Skills:" in prompt
    assert "Candidate Experience:" in prompt


# --- Tests for parse_llm_response ---

@pytest.mark.parametrize(
    "llm_output, expected_score, expected_body_contains",
    [
        ("FIT_SCORE: 85\nDear Hiring Manager,\nI am writing to apply...", 85, "Dear Hiring Manager"),
        ("FIT_SCORE: 92/100\nParagraph 1\nParagraph 2", 92, "Paragraph 1"),
        ("I am excited about this role.\nFIT_SCORE: 78\nThank you.", 78, "I am excited about this role."),
        ("No score provided here.\nJust body text.", 75, "No score provided here."),  # Default score fallback
        ("FIT_SCORE: N/A\nBody text.", 75, "Body text."),  # Unparseable score fallback
    ],
)
def test_parse_llm_response(llm_output, expected_score, expected_body_contains):
    body, score, key_alignments, missing_skills = evaluator.parse_llm_response(llm_output)
    assert score == expected_score
    assert expected_body_contains in body


def test_parse_llm_response_json():
    json_raw = json.dumps({
        "fit_score": 88,
        "cover_letter_body": "Dear Manager,\n\nI am applying for the role.",
        "key_alignments": ["Python experience", "Architecture background"],
        "missing_skills": ["Kubernetes"]
    })
    body, score, alignments, missing = evaluator.parse_llm_response(json_raw)
    assert score == 88
    assert "Dear Manager" in body
    assert alignments == ["Python experience", "Architecture background"]
    assert missing == ["Kubernetes"]


def test_parse_llm_response_json_in_markdown_fence():
    json_raw = """```json
    {
        "fit_score": 90,
        "cover_letter_body": "Clean body inside markdown block.",
        "key_alignments": ["Golang"],
        "missing_skills": []
    }
    ```"""
    body, score, alignments, missing = evaluator.parse_llm_response(json_raw)
    assert score == 90
    assert body == "Clean body inside markdown block."
    assert alignments == ["Golang"]


def test_parse_llm_response_json_invalid_list_types():
    # Valid JSON where key_alignments/missing_skills are not lists
    json_raw = json.dumps({
        "fit_score": 70,
        "cover_letter_body": "Body text",
        "key_alignments": "Invalid non-list value",
        "missing_skills": None
    })
    body, score, alignments, missing = evaluator.parse_llm_response(json_raw)
    assert score == 70
    assert alignments == []
    assert missing == []


# --- Tests for query_ollama ---

@patch("subprocess.run")
def test_query_ollama_success(mock_run):
    mock_run.return_value = MagicMock(stdout="FIT_SCORE: 90\nGreat fit!")
    response = evaluator.query_ollama("Test Prompt", model="llama3.2")

    mock_run.assert_called_once_with(
        ["ollama", "run", "llama3.2", "Test Prompt"],
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8"
    )
    assert "FIT_SCORE: 90" in response


@patch("subprocess.run")
def test_query_ollama_failure(mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd="ollama", stderr="Model not found"
    )
    with pytest.raises(RuntimeError, match="Ollama execution failed"):
        evaluator.query_ollama("Test Prompt")


@patch("subprocess.run")
def test_query_ollama_file_not_found(mock_run):
    mock_run.side_effect = FileNotFoundError("ollama binary not found")
    with pytest.raises(RuntimeError, match="Ollama execution failed"):
        evaluator.query_ollama("Test Prompt")


# --- Integration Test for evaluate_job ---

@patch("evaluator.query_ollama")
def test_evaluate_job(mock_query, sample_cv, tmp_path):
    # Setup temporary JSON CV
    cv_file = tmp_path / "candidate.json"
    cv_file.write_text(json.dumps(sample_cv), encoding="utf-8")

    mock_query.return_value = "FIT_SCORE: 88\nI am an ideal candidate."

    body, score, key_alignments, missing_skills = evaluator.evaluate_job(
        cv_path=str(cv_file),
        job_description="Backend engineer needed."
    )

    assert score == 88
    assert body == "I am an ideal candidate."
    mock_query.assert_called_once()
