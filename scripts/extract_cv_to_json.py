#!/usr/bin/env python3
"""
Robust utility script to extract complete structured JSON data from LaTeX CV files,
including full contact identity (Name, Address, Phone, Email, LinkedIn) for LaTeX rendering.
"""

import argparse
import json
import os
import re
import sys

DEFAULT_INPUT_TEX = "cv_developer.tex"
DEFAULT_OUTPUT_JSON = "cv_configs/developer.json"


def clean_latex(text: str) -> str:
    """Strips common LaTeX tags and returns clean plain text."""
    if not text:
        return ""

    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\\href\{[^\}]*\}\{([^\}]*)\}", r"\1", text)
    text = re.sub(r"\\(?:textbf|textit|emph|underline|cventry|cvitem)\{([^\}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^\}]*\})?", " ", text)
    text = re.sub(r"\\\\", "\n", text)
    text = re.sub(r"[{}]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def parse_complete_latex_cv(tex_content: str) -> dict:
    """Parses full LaTeX CV content into a structured dictionary."""
    cv_data = {
        "basics": {
            "name": "",
            "address": "",
            "email": "",
            "phone": "",
            "linkedin": "",
        },
        "summary": "",
        "skills": [],
        "experience": [],
        "education": [],
        "certifications": [],
        "raw_sections": {},
    }

    # --- 1. EXTRACT HEADER / CENTER BLOCK (NAME & ADDRESS) ---
    header_block_match = re.search(
        r"%?\s*Header.*?\\begin\{center\}(.*?)\\end\{center\}",
        tex_content,
        re.DOTALL | re.IGNORECASE,
    )

    if not header_block_match:
        # Fallback to any centered block near the top of the document
        header_block_match = re.search(
            r"\\begin\{center\}(.*?)\\end\{center\}",
            tex_content,
            re.DOTALL | re.IGNORECASE,
        )

    if header_block_match:
        header_text = header_block_match.group(1)
        lines = [line.strip() for line in header_text.splitlines() if line.strip()]
        cleaned_lines = []

        for line in lines:
            cleaned = clean_latex(line)
            if cleaned:
                cleaned_lines.append(cleaned)

        # First clean line in center environment is the candidate's Name
        if cleaned_lines:
            cv_data["basics"]["name"] = cleaned_lines[0]

        # Scan subsequent lines for Address patterns
        for line in cleaned_lines[1:]:
            # Matches Australian state/postcode patterns or general street lines
            if re.search(r"\b(?:VIC|NSW|QLD|WA|SA|TAS|ACT|NT)\b|\b\d{4}\b", line, re.IGNORECASE) or re.search(r"\d+\s+[A-Za-z]+", line):
                cv_data["basics"]["address"] = line
                break
            # Fallback line if it's not contact URLs or numbers
            elif not any(k in line.lower() for k in ["@", "http", "linkedin", "+61", "04"]):
                if not cv_data["basics"]["address"] and len(line) > 5:
                    cv_data["basics"]["address"] = line

    # --- FALLBACK NAME EXTRACTION ---
    if not cv_data["basics"]["name"]:
        name_match = re.search(r"\\name(?:\{([^\}]*)\})?(?:\{([^\}]*)\})?", tex_content)
        if name_match and (name_match.group(1) or name_match.group(2)):
            part1 = name_match.group(1) or ""
            part2 = name_match.group(2) or ""
            cv_data["basics"]["name"] = f"{part1} {part2}".strip()

    if not cv_data["basics"]["name"]:
        author_match = re.search(r"\\(?:author|candidate|fullname)\{([^\}]*)\}", tex_content, re.IGNORECASE)
        if author_match:
            cv_data["basics"]["name"] = clean_latex(author_match.group(1))

    # --- FALLBACK ADDRESS EXTRACTION ---
    if not cv_data["basics"]["address"]:
        addr_match = re.search(r"\\address(?:\{([^\}]*)\})?(?:\{([^\}]*)\})?", tex_content)
        if addr_match and (addr_match.group(1) or addr_match.group(2)):
            line1 = clean_latex(addr_match.group(1) or "")
            line2 = clean_latex(addr_match.group(2) or "")
            cv_data["basics"]["address"] = f"{line1}, {line2}".strip(", ")

    if not cv_data["basics"]["address"]:
        aus_addr = re.search(r"(?:[0-9A-Za-z\s,\/\-]+,\s*)?[A-Za-z\s]+\s+(?:VIC|NSW|QLD|WA|SA|TAS|ACT|NT)\s+\d{4}", tex_content, re.IGNORECASE)
        if aus_addr:
            cv_data["basics"]["address"] = clean_latex(aus_addr.group(0))

    # --- CONTACT DETAILS (EMAIL, PHONE, LINKEDIN) ---
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", tex_content)
    if email_match:
        cv_data["basics"]["email"] = email_match.group(0)

    phone_match = re.search(r"\+?\d[\d\s\-]{8,15}\d", tex_content)
    if phone_match:
        cv_data["basics"]["phone"] = phone_match.group(0).strip()

    linkedin_macro = re.search(r"\\(?:linkedin|social\[linkedin\])\{([^\}]*)\}", tex_content, re.IGNORECASE)
    if linkedin_macro:
        val = clean_latex(linkedin_macro.group(1))
        cv_data["basics"]["linkedin"] = val if val.startswith("http") else f"https://linkedin.com/in/{val}"
    else:
        linkedin_match = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-]+", tex_content, re.IGNORECASE)
        if linkedin_match:
            raw_url = linkedin_match.group(0)
            cv_data["basics"]["linkedin"] = raw_url if raw_url.startswith("http") else f"https://{raw_url}"

    # --- PARSE CV SECTIONS ---
    section_splits = re.split(r"\\section\*?\{([^\}]*)\}", tex_content, flags=re.IGNORECASE)

    header_clean = clean_latex(section_splits[0])
    if header_clean:
        cv_data["raw_sections"]["header"] = header_clean

    for i in range(1, len(section_splits), 2):
        sec_title = section_splits[i].strip()
        sec_body = section_splits[i + 1] if (i + 1) < len(section_splits) else ""
        sec_title_lower = sec_title.lower()

        if any(k in sec_title_lower for k in ["skill", "expertise", "competenc", "technologies"]):
            bullets = re.findall(r"\\item\s+(.*?)(?=\\item|\\end\{itemize\}|\\\\|$)", sec_body, re.DOTALL)
            if bullets:
                cv_data["skills"].extend([clean_latex(b) for b in bullets if clean_latex(b)])
            else:
                raw_text = clean_latex(sec_body)
                items = [item.strip() for item in re.split(r"[,•\n]", raw_text) if item.strip()]
                cv_data["skills"].extend(items)

        elif any(k in sec_title_lower for k in ["experience", "employment", "history", "career"]):
            role_chunks = re.findall(r"(.*?)(?:\\begin\{itemize\}(.*?)\\end\{itemize\}|$)", sec_body, re.DOTALL)

            for chunk_header, chunk_items in role_chunks:
                clean_header = clean_latex(chunk_header)
                if not clean_header and not chunk_items:
                    continue

                bullets = re.findall(r"\\item\s+(.*?)(?=\\item|$)", chunk_items, re.DOTALL) if chunk_items else []
                clean_bullets = [clean_latex(b) for b in bullets if clean_latex(b)]

                if clean_header or clean_bullets:
                    cv_data["experience"].append({
                        "role_header": clean_header.replace("\n", " "),
                        "highlights": clean_bullets,
                    })

        elif any(k in sec_title_lower for k in ["certif", "license", "training", "accreditat", "professional development"]):
            bullets = re.findall(r"\\item\s+(.*?)(?=\\item|\\end\{itemize\}|\\\\|$)", sec_body, re.DOTALL)
            if bullets:
                cv_data["certifications"].extend([clean_latex(b) for b in bullets if clean_latex(b)])
            else:
                cleaned = clean_latex(sec_body)
                cv_data["certifications"].extend([line.strip() for line in cleaned.split("\n") if line.strip()])

        elif "education" in sec_title_lower or "academic" in sec_title_lower:
            bullets = re.findall(r"\\item\s+(.*?)(?=\\item|\\end\{itemize\}|\\\\|$)", sec_body, re.DOTALL)
            if bullets:
                cv_data["education"].extend([clean_latex(b) for b in bullets if clean_latex(b)])
            else:
                cleaned = clean_latex(sec_body)
                cv_data["education"].extend([line.strip() for line in cleaned.split("\n") if line.strip()])

        elif any(k in sec_title_lower for k in ["summary", "profile", "about"]):
            cv_data["summary"] = clean_latex(sec_body)

        else:
            cv_data["raw_sections"][sec_title] = clean_latex(sec_body)

    return cv_data


def main():
    parser = argparse.ArgumentParser(
        description="Extract complete structured JSON data from LaTeX CV files.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""Examples:
  python3 scripts/extract_cv_to_json.py -i cv_developer.tex -o cv_configs/developer.json
""",
    )

    parser.add_argument(
        "-i",
        "--input",
        default=DEFAULT_INPUT_TEX,
        metavar="PATH",
        help=f"Path to input LaTeX CV file (default: '{DEFAULT_INPUT_TEX}')",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT_JSON,
        metavar="PATH",
        help=f"Path to output JSON file (default: '{DEFAULT_OUTPUT_JSON}')",
    )

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"❌ Input file '{args.input}' not found.\n")
        parser.print_help()
        sys.exit(1)

    print(f"📖 Reading LaTeX CV from '{args.input}'...")
    with open(args.input, "r", encoding="utf-8") as f:
        tex_content = f.read()

    print("⚡ Parsing full work history, contact identity (Name, Address, Phone, Email, LinkedIn)...")
    cv_data = parse_complete_latex_cv(tex_content)

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(cv_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Extraction Summary:")
    print(f"   • Name:     {cv_data['basics']['name'] or '❌ Missing'}")
    print(f"   • Address:  {cv_data['basics']['address'] or '❌ Missing'}")
    print(f"   • Email:    {cv_data['basics']['email'] or '❌ Missing'}")
    print(f"   • Phone:    {cv_data['basics']['phone'] or '❌ Missing'}")
    print(f"   • LinkedIn: {cv_data['basics']['linkedin'] or '❌ Missing'}")
    print(f"\n💾 Saved structured JSON to '{args.output}'.")


if __name__ == "__main__":
    main()
