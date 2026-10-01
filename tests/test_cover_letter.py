import os
import subprocess
from unittest.mock import MagicMock, patch
import pytest
import re
import json

from cover_letter import (
    cleanup_build_artifacts,
    get_cover_letter_paths,
    render_latex_cover_letter,
    sanitize_filename,
    extract_cover_letter_body,
)

# --- Fixtures ---

@pytest.fixture
def sample_cv():
    return {
        "basics": {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "0400000000"
        }
    }


@pytest.fixture
def latex_template(tmp_path):
    template_file = tmp_path / "template.tex"
    content = r"""
\documentclass{article}
\begin{document}
Name: <<NAME>>
Email: <<EMAIL>>
Phone: <<PHONE>>
Body: <<BODY>>
\end{document}
"""
    template_file.write_text(content, encoding="utf-8")
    return str(template_file)


# --- Unit Tests ---

def test_sanitize_filename():
    assert sanitize_filename("Acme Corp / Inc.") == "AcmeCorpInc"
    assert sanitize_filename("Senior C++ Developer (#1)") == "SeniorCDeveloper1"
    assert sanitize_filename(None) == ""


def test_get_cover_letter_paths():
    tex_path, pdf_path = get_cover_letter_paths(os.path.join("output", "pdfs"), "Acme / Co", "Dev #1")
    assert tex_path == os.path.join("output", "pdfs", "CoverLetter_AcmeCo_Dev1.tex")
    assert pdf_path == os.path.join("output", "pdfs", "CoverLetter_AcmeCo_Dev1.pdf")

def test_cleanup_build_artifacts(tmp_path):
    base_tex = tmp_path / "CoverLetter.tex"
    aux_file = tmp_path / "CoverLetter.aux"
    log_file = tmp_path / "CoverLetter.log"
    out_file = tmp_path / "CoverLetter.out"

    base_tex.write_text("tex", encoding="utf-8")
    aux_file.write_text("aux", encoding="utf-8")
    log_file.write_text("log", encoding="utf-8")
    out_file.write_text("out", encoding="utf-8")

    cleanup_build_artifacts(str(base_tex))

    # .tex should remain, auxiliary files should be deleted
    assert base_tex.exists()
    assert not aux_file.exists()
    assert not log_file.exists()
    assert not out_file.exists()


@patch("subprocess.run")
def test_render_latex_cover_letter_success_and_cleanup(mock_run, sample_cv, latex_template, tmp_path):
    output_tex = str(tmp_path / "output" / "pdfs" / "CoverLetter.tex")
    output_pdf = str(tmp_path / "output" / "pdfs" / "CoverLetter.pdf")
    
    # Simulate pdflatex creating intermediate auxiliary files and the target PDF
    os.makedirs(os.path.dirname(output_tex), exist_ok=True)
    aux_file = tmp_path / "output" / "pdfs" / "CoverLetter.aux"
    log_file = tmp_path / "output" / "pdfs" / "CoverLetter.log"
    out_file = tmp_path / "output" / "pdfs" / "CoverLetter.out"
    aux_file.write_text("aux content", encoding="utf-8")
    log_file.write_text("log content", encoding="utf-8")
    out_file.write_text("out content", encoding="utf-8")

    # Ensure the PDF exists when mock_run is called
    def side_effect(*args, **kwargs):
        with open(output_pdf, "w") as f:
            f.write("mock pdf content")
        return MagicMock(returncode=0)

    mock_run.side_effect = side_effect

    # Execute LaTeX rendering
    success = render_latex_cover_letter(sample_cv, "Cover letter body.", latex_template, output_tex)

    # Assert rendering succeeded and artifacts were cleaned up
    assert success is True
    assert not os.path.exists(aux_file)
    assert not os.path.exists(log_file)
    assert not os.path.exists(out_file)


@patch("subprocess.run", side_effect=FileNotFoundError("pdflatex missing"))
def test_render_latex_cover_letter_pdflatex_missing(mock_run, sample_cv, latex_template, tmp_path):
    output_tex = str(tmp_path / "output.tex")

    success = render_latex_cover_letter(sample_cv, "Body without PDF.", latex_template, output_tex)

    # TeX file is generated cleanly even if pdflatex is not installed locally
    assert success is False
    assert os.path.exists(output_tex)


# Use the production extract_cover_letter_body imported above.

def test_extract_cover_letter_body_valid_json():
    raw_input = '{"cover_letter_body": "Dear Hiring Manager..."}'
    assert extract_cover_letter_body(raw_input) == "Dear Hiring Manager..."

def test_extract_cover_letter_body_stacked_json_regex():
    raw_input = '{"meta": "data"}\n{"cover_letter_body": "Extracted via regex..."}'
    assert extract_cover_letter_body(raw_input) == "Extracted via regex..."

def test_extract_cover_letter_body_fallback_plain_text():
    raw_input = "```json\nDear Hiring Manager, here is plain text.\n```"
    assert extract_cover_letter_body(raw_input) == "Dear Hiring Manager, here is plain text."