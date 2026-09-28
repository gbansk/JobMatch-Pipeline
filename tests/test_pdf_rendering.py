#!/usr/bin/env python3
"""
Fast LaTeX Compilation Test with Debug Logging and Edge-Case Coverage
"""

import json
import os
import sys
from unittest.mock import patch

# Ensure root directory is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from cover_letter import render_latex_cover_letter


def test_fast_pdf_generation():
    profile_path = os.path.join(ROOT_DIR, "profiles", "developer.json")
    if os.path.exists(profile_path):
        with open(profile_path, "r", encoding="utf-8") as f:
            cv_data = json.load(f)
    else:
        cv_data = {
            "basics": {
                "name": "Gary Bell",
                "email": "gary.bell@example.com",
                "phone": "+61 419 345 534",
                "location": {
                    "address": "PO Box 110 Mill Park Victoria 3082"
                }
            }
        }

    mock_body = (
        "I am writing to express my strong interest in the Senior Full Stack Engineer position at "
        "Woolworths Group. With extensive experience delivering high-value software systems, "
        "I have a proven track record of implementing robust engineering frameworks.\n\n"
        
        "Throughout my career, I have specialized in Golang, .NET Core, and Python. "
        "My expertise in building secure microservices aligns directly with your technical goals.\n\n"
        
        "I look forward to bringing my technical leadership to your team."
    )

    template_path = os.path.join(ROOT_DIR, "cover_letter_template.tex")
    output_tex = os.path.join(ROOT_DIR, "output", "test_fast_output.tex")
    company = "Woolworths Group"

    success = render_latex_cover_letter(
        cv_data=cv_data,
        body_text=mock_body,
        template_path=template_path,
        output_tex=output_tex,
        company=company
    )

    if not success:
        log_file = os.path.join(ROOT_DIR, "output", "test_fast_output.log")
        print("\n" + "="*50)
        print("LATEX COMPILATION ERROR LOG:")
        print("="*50)
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                # Print lines starting with ! or ? (LaTeX error indicators)
                errors = [line for line in lines if line.startswith("!") or "Error" in line]
                if errors:
                    print("".join(errors))
                else:
                    print("".join(lines[-30:]))
        else:
            print("No log file found.")
        print("="*50 + "\n")

    assert success is True, "PDF compilation failed!"


def test_render_latex_missing_template(tmp_path):
    """Test behavior when the template file does not exist."""
    output_tex = str(tmp_path / "output.tex")
    success = render_latex_cover_letter(
        cv_data={},
        body_text="Test body",
        template_path="non_existent_template.tex",
        output_tex=output_tex
    )
    assert success is False


@patch("subprocess.run")
def test_render_latex_pdflatex_not_found(mock_run, tmp_path):
    """Test behavior when pdflatex executable is not found on PATH."""
    mock_run.side_effect = FileNotFoundError("pdflatex not found")

    template_file = tmp_path / "template.tex"
    template_file.write_text("Standard TeX template with CANDIDATENAME", encoding="utf-8")
    output_tex = str(tmp_path / "output" / "CoverLetter.tex")

    success = render_latex_cover_letter(
        cv_data={"basics": {"name": "Gary Bell"}},
        body_text="Test body",
        template_path=str(template_file),
        output_tex=output_tex
    )
    assert success is False


def test_render_latex_missing_optional_basics(tmp_path):
    """Test rendering when candidate contact details are partially missing."""
    template_file = tmp_path / "template.tex"
    template_file.write_text(
        "Name: __CANDIDATE_NAME__\nEmail: __CANDIDATE_EMAIL__\nBody: <<BODY>>",
        encoding="utf-8"
    )
    output_tex = str(tmp_path / "output" / "CoverLetter.tex")

    sparse_cv = {"basics": {"name": "Gary Bell"}}  # Missing phone, email, address

    render_latex_cover_letter(
        sparse_cv,
        "Paragraph 1\n\nParagraph 2",
        str(template_file),
        output_tex
    )
    assert os.path.exists(output_tex)
    
    with open(output_tex, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Gary Bell" in content


def test_render_latex_escaping_special_characters(tmp_path):
    """Test LaTeX character escaping during placeholder substitution."""
    template_file = tmp_path / "template.tex"
    template_file.write_text("Company: __COMPANY__\nBody: <<BODY>>", encoding="utf-8")
    output_tex = str(tmp_path / "output" / "CoverLetter.tex")

    cv_data = {"basics": {"name": "Gary Bell"}}
    body_with_special_chars = "Testing 100% success rate & high $ earned."
    company_name = "A&B Co. $100%_Special#Chars"

    render_latex_cover_letter(
        cv_data,
        body_with_special_chars,
        str(template_file),
        output_tex,
        company=company_name
    )

    with open(output_tex, "r", encoding="utf-8") as f:
        content = f.read()

    assert r"A\&B Co. \$100\%\_Special\#Chars" in content
    assert r"100\%" in content
    assert r"\&" in content
    assert r"\$" in content


if __name__ == "__main__":
    test_fast_pdf_generation()
