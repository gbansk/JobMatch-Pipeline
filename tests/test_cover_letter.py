import os
import subprocess
from unittest.mock import MagicMock, patch
import pytest
import re
import json

from cover_letter import (
    escape_latex_chars,
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

# --- 1. Test LaTeX Character Escaping ---

def test_escape_latex_chars():
    assert escape_latex_chars("") == ""
    assert escape_latex_chars(None) == ""
    
    # Check special characters escaping
    raw_text = r"100% & $50 #1_test {item} ~ ^ \ "
    escaped = escape_latex_chars(raw_text)
    assert r"\%" in escaped
    assert r"\&" in escaped
    assert r"\$" in escaped
    assert r"\#" in escaped
    assert r"\_" in escaped
    assert r"\{" in escaped
    assert r"\}" in escaped
    assert r"\textasciitilde{}" in escaped
    assert r"\textasciicircum{}" in escaped
    assert r"\textbackslash\{\}" in escaped


# --- 2. Test Template Not Found ---

def test_render_latex_cover_letter_missing_template(tmp_path):
    output_tex = str(tmp_path / "output.tex")
    success = render_latex_cover_letter({}, "Body", "non_existent_template.tex", output_tex)
    assert success is False


# --- 3. Test CV Data Extraction Fallbacks ---

@patch("subprocess.run")
def test_render_latex_cover_letter_cv_data_fallbacks(mock_run, tmp_path):
    template_file = tmp_path / "template.tex"
    template_file.write_text("Name: __CANDIDATE_NAME__ Phone: __CANDIDATE_PHONE__ Addr: __CANDIDATE_ADDRESS__", encoding="utf-8")
    output_tex = str(tmp_path / "output.tex")

    # Wrapped cv_data structure with nested 'basics' for mobile/phone
    nested_cv = {
        "data": {
            "candidate_name": "Fallback Name",
            "basics": {
                "mobile": "0411111111"
            },
            "location": {"city": "Melbourne"}
        }
    }

    render_latex_cover_letter(nested_cv, "Sample body.", str(template_file), output_tex)

    rendered = (tmp_path / "output.tex").read_text(encoding="utf-8")
    assert "Fallback Name" in rendered
    assert "0411111111" in rendered
    assert "Melbourne" in rendered
    

# --- 5. Test OSError in Artifact Cleanup ---

def test_cleanup_build_artifacts_os_error(tmp_path):
    aux_file = tmp_path / "CoverLetter.aux"
    aux_file.write_text("aux", encoding="utf-8")

    # Mock os.remove to raise OSError
    with patch("os.remove", side_effect=OSError("Permission denied")):
        # Should catch OSError without raising an exception
        cleanup_build_artifacts(str(tmp_path / "CoverLetter.tex"))


# --- Additional Fallback & Edge Case Tests ---

@patch("subprocess.run")
def test_render_latex_cover_letter_field_fallbacks(mock_run, tmp_path):
    template_file = tmp_path / "template.tex"
    template_file.write_text(
        "Name: __CANDIDATE_NAME__ Phone: __CANDIDATE_PHONE__ Email: __CANDIDATE_EMAIL__ Addr: __CANDIDATE_ADDRESS__", 
        encoding="utf-8"
    )
    output_tex = str(tmp_path / "output.tex")

    # 1) Direct root keys and string location fallback
    cv_data_1 = {
        "name": "Root Name",
        "phone": "0400111222",
        "email": "root@example.com",
        "location": "Sydney, NSW"
    }
    render_latex_cover_letter(cv_data_1, "Body text.", str(template_file), output_tex)
    rendered_1 = (tmp_path / "output.tex").read_text(encoding="utf-8")
    assert "Root Name" in rendered_1
    assert "0400111222" in rendered_1
    assert "root@example.com" in rendered_1
    assert "Sydney, NSW" in rendered_1

    # 2) Default "Gary Bell" name fallback
    cv_data_2 = {}
    render_latex_cover_letter(cv_data_2, "Body text.", str(template_file), output_tex)
    rendered_2 = (tmp_path / "output.tex").read_text(encoding="utf-8")
    assert "Gary Bell" in rendered_2


@patch("subprocess.run")
def test_render_latex_cover_letter_json_body_variations(mock_run, tmp_path):
    template_file = tmp_path / "template.tex"
    template_file.write_text("Body: <<BODY>> Para1: __PARA1__ Para2: __PARA2__", encoding="utf-8")
    output_tex = str(tmp_path / "output.tex")

    # 1) Embedded JSON list inside body string
    json_list_body = '{"cover_letter_body": ["First paragraph.", "Second paragraph."]}'
    render_latex_cover_letter({}, json_list_body, str(template_file), output_tex)
    rendered_list = (tmp_path / "output.tex").read_text(encoding="utf-8")
    assert "First paragraph." in rendered_list
    assert "Second paragraph." in rendered_list

    # 2) Direct JSON object without list regex match
    json_direct_body = '{"cover_letter_body": "Direct parsed paragraph."}'
    render_latex_cover_letter({}, json_direct_body, str(template_file), output_tex)
    rendered_direct = (tmp_path / "output.tex").read_text(encoding="utf-8")
    assert "Direct parsed paragraph." in rendered_direct

    # 3) Invalid JSON starting with '{' triggering JSONDecodeError fallback
    invalid_json_body = '{"cover_letter_body": bad json syntax'
    render_latex_cover_letter({}, invalid_json_body, str(template_file), output_tex)
    rendered_invalid = (tmp_path / "output.tex").read_text(encoding="utf-8")
    assert "bad json syntax" in rendered_invalid


@patch("subprocess.run")
def test_render_latex_cover_letter_line_break_cleanup(mock_run, tmp_path):
    template_file = tmp_path / "template.tex"
    # Create artificial double backslashes and line breaks
    template_file.write_text("Header \\\\ \n \\\\ \n Body text.", encoding="utf-8")
    output_tex = str(tmp_path / "output.tex")

    render_latex_cover_letter({}, "Body text.", str(template_file), output_tex)
    rendered = (tmp_path / "output.tex").read_text(encoding="utf-8")
    assert "\\\\ \n \\\\ \n" not in rendered


import os
import json
from unittest.mock import patch
from cover_letter import cleanup_build_artifacts, render_latex_cover_letter

def test_cover_letter_uncovered_paths(tmp_path):
    # 1. Test extra build artifact extensions (.toc, .fls, .fdb_latexmk)
    base_tex = tmp_path / "test.tex"
    toc_file = tmp_path / "test.toc"
    toc_file.write_text("toc", encoding="utf-8")
    cleanup_build_artifacts(str(base_tex))
    assert not toc_file.exists()

    # 2. Test nested dict location + nested json string body parsing
    template_file = tmp_path / "template.tex"
    template_file.write_text(
        "Addr: __CANDIDATE_ADDRESS__ Body: <<BODY>> Para3: __PARA3__", 
        encoding="utf-8"
    )
    output_tex = str(tmp_path / "output.tex")

    cv_data = {
        "basics": {
            "name": "Jane",
            "location": {"full_address": "123 Main St"}
        }
    }
    # Body string formatted as direct JSON object
    json_body = json.dumps({"cover_letter_body": ["P1", "P2", "P3"]})

    with patch("subprocess.run"):
        render_latex_cover_letter(cv_data, json_body, str(template_file), output_tex)

    content = (tmp_path / "output.tex").read_text(encoding="utf-8")
    assert "123 Main St" in content
    assert "P3" in content