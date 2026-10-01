#!/usr/bin/env python3
"""
Cover Letter Generation Engine:
Handles filename sanitization, LaTeX template rendering, pdflatex execution,
and intermediate compilation artifact cleanup.
"""

import json
import os
import re
import subprocess
from datetime import datetime


def escape_latex_chars(text: str) -> str:
    """Escapes special LaTeX characters in dynamic text bodies."""
    if not text:
        return ""
    # Order matters: backslash must be handled first if present
    text = text.replace("\\", r"\textbackslash{}")
    chars = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for char, replacement in chars.items():
        text = text.replace(char, replacement)
    return text


def sanitize_filename(text: str) -> str:
    """Removes non-alphanumeric characters for safe file path creation."""
    return re.sub(r"[^a-zA-Z0-9]", "", text or "")


def get_cover_letter_paths(output_dir: str, company: str, title: str) -> tuple[str, str]:
    """Generates sanitized output paths for .tex and .pdf cover letter files."""
    safe_company = sanitize_filename(company) or "Company"
    safe_title = sanitize_filename(title) or "Position"
    base_name = f"CoverLetter_{safe_company}_{safe_title}"
    output_tex = os.path.join(output_dir, f"{base_name}.tex")
    output_pdf = os.path.join(output_dir, f"{base_name}.pdf")
    return output_tex, output_pdf


def cleanup_build_artifacts(output_tex: str) -> None:
    """Removes intermediate LaTeX compilation artifacts (.aux, .log, .out, etc.)."""
    base_path = os.path.splitext(output_tex)[0]
    for ext in [".aux", ".log", ".out", ".toc", ".fls", ".fdb_latexmk"]:
        artifact = base_path + ext
        if os.path.exists(artifact):
            try:
                os.remove(artifact)
            except OSError:
                pass


def render_latex_cover_letter(
    cv_data: dict,
    body_text: str,
    template_path: str,
    output_tex: str,
    company: str = "Company"
) -> bool:
    """Fills LaTeX template placeholders, compiles to PDF, and cleans up artifacts."""
    if not os.path.exists(template_path):
        print(f"Error: Template file not found at {template_path}")
        return False

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    # Unwrap nested cv_data if needed
    if isinstance(cv_data, dict) and "data" in cv_data and isinstance(cv_data["data"], dict):
        cv_data = cv_data["data"]

    basics = cv_data.get("basics", {}) if isinstance(cv_data, dict) else {}

    # Extract details with fallback keys
    cand_name = (
        basics.get("name") 
        or cv_data.get("name") 
        or cv_data.get("candidate_name") 
        or "Gary Bell"
    )
    cand_phone = (
        basics.get("phone") 
        or basics.get("mobile") 
        or cv_data.get("phone") 
        or ""
    )
    cand_email = (
        basics.get("email") 
        or cv_data.get("email") 
        or ""
    )

    location = basics.get("location", cv_data.get("location", {}))
    if isinstance(location, dict):
        cand_address = (
            location.get("address") 
            or location.get("full_address") 
            or location.get("city") 
            or ""
        )
    else:
        cand_address = str(location or "")

    # Robust extraction of cover_letter_body if text contains raw or stacked JSON
    body_text = extract_cover_letter_body(body_text)
    
    # Format body paragraphs
    paragraphs = [p.strip() for p in body_text.split("\n\n") if p.strip()]
    para1 = paragraphs[0] if len(paragraphs) > 0 else body_text
    para2 = paragraphs[1] if len(paragraphs) > 1 else ""
    para3 = paragraphs[2] if len(paragraphs) > 2 else ""

    # Escape dynamic values for LaTeX safety
    esc_name = escape_latex_chars(cand_name)
    esc_address = escape_latex_chars(cand_address)
    esc_phone = escape_latex_chars(cand_phone)
    esc_email = escape_latex_chars(cand_email)
    esc_company = escape_latex_chars(company)

    esc_p1 = escape_latex_chars(para1)
    esc_p2 = escape_latex_chars(para2)
    esc_p3 = escape_latex_chars(para3)
    esc_body = escape_latex_chars(body_text)

    # Perform Template Placeholder Replacements
    filled = template

    # Double-underscore placeholders from template
    filled = filled.replace("__CANDIDATE_NAME__", esc_name)
    filled = filled.replace("__CANDIDATE_ADDRESS__", esc_address)
    filled = filled.replace("__CANDIDATE_PHONE__", esc_phone)
    filled = filled.replace("__CANDIDATE_EMAIL__", esc_email)
    filled = filled.replace("__COMPANY__", esc_company)

    # Standard placeholders
    filled = filled.replace("CANDIDATENAME", esc_name)
    filled = filled.replace("CANDIDATEADDRESS", esc_address)
    filled = filled.replace("CANDIDATEPHONE", esc_phone)
    filled = filled.replace("CANDIDATEEMAIL", esc_email)
    filled = filled.replace("COMPANY", esc_company)
    filled = filled.replace("<<DATE>>", datetime.now().strftime("%B %d, %Y"))

    # Body Paragraph Replacements
    filled = filled.replace("__PARA1__", esc_p1)
    filled = filled.replace("__PARA2__", esc_p2)
    filled = filled.replace("__PARA3__", esc_p3)
    filled = filled.replace("PARAI", esc_p1)
    filled = filled.replace("PARA1", esc_p1)
    filled = filled.replace("PARA2", esc_p2)
    filled = filled.replace("PARA3", esc_p3)
    filled = filled.replace("<<BODY>>", esc_body)

    output_dir = os.path.dirname(output_tex) or "."
    os.makedirs(output_dir, exist_ok=True)

    # Prevent double line breaks caused by missing contact information
    filled = re.sub(r'(\\\s*){2,}', r'\\\\ ', filled)
    filled = re.sub(r'\\\\\s*\n\s*\\\\\s*\n', r'\\\\ \n', filled)

    with open(output_tex, "w", encoding="utf-8") as f:
        f.write(filled)

    expected_pdf = os.path.splitext(output_tex)[0] + ".pdf"
    pdf_compiled = False

    try:
        subprocess.run(
            ["pdflatex", "-interaction=batchmode", f"-output-directory={output_dir}", output_tex],
            capture_output=True,
            check=False
        )
        pdf_compiled = os.path.exists(expected_pdf)
    except FileNotFoundError:
        pdf_compiled = False
    finally:
        cleanup_build_artifacts(output_tex)

    return pdf_compiled


def extract_cover_letter_body(body_text: str) -> str:
    """Extracts cover letter body text from raw text, JSON strings, or stacked JSON structures."""
    if not isinstance(body_text, str):
        return str(body_text or "")

    if "cover_letter_body" in body_text or body_text.strip().startswith("{"):
        match = re.search(r'"cover_letter_body"\s*:\s*("(?:[^"\\]|\\.)*"|\[[^\]]*\])', body_text, re.DOTALL)
        if match:
            try:
                extracted = json.loads(match.group(1))
                if isinstance(extracted, list):
                    return "\n\n".join(extracted)
                return str(extracted)
            except json.JSONDecodeError:
                pass
        else:
            try:
                parsed = json.loads(body_text)
                return str(parsed.get("cover_letter_body", body_text))
            except json.JSONDecodeError:
                pass

    return re.sub(r'^```(?:json)?\s*|\s*```$', '', body_text.strip(), flags=re.MULTILINE)
