#!/usr/bin/env python3
"""
Utility script to extract structured JSON data from a raw LaTeX CV source file.
"""

import argparse
import json
import os
import re
import sys

DEFAULT_INPUT_TEX = "resume.tex"
DEFAULT_OUTPUT_JSON = "cv_data.json"


def strip_latex_formatting(text: str) -> str:
    """Strips common LaTeX markup tags and leaves plain text."""
    if not text:
        return ""

    # Remove comments
    text = re.sub(r"%.*", "", text)

    # Replace commands like \textbf{word}, \emph{word}, \href{url}{word} with inner text
    text = re.sub(r"\\href\{[^\}]*\}\{([^\}]*)\}", r"\1", text)
    text = re.sub(r"\\(?:textbf|textit|emph|cventry|cvitem)\{([^\}]*)\}", r"\1", text)

    # Remove remaining lone LaTeX commands (e.g., \small, \vspace{...}, \\)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^\}]*\})?", " ", text)
    text = re.sub(r"\\\\", "\n", text)
    text = re.sub(r"[{}]", "", text)

    # Clean up excess whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    return text.strip()


def parse_latex_cv(tex_content: str) -> dict:
    """Parses raw LaTeX CV content into a structured dictionary matching cv_data.json schema."""
    cv_data = {
        "basics": {
            "name": "",
            "title": "",
            "email": "",
            "phone": "",
            "location": "",
        },
        "summary": "",
        "skills": [],
        "experience": [],
        "education": [],
    }

    # 1. Extract Name/Basics from header commands if present
    name_match = re.search(r"\\name\{([^\}]*)\}\{([^\}]*)\}", tex_content)
    if name_match:
        cv_data["basics"]["name"] = f"{name_match.group(1)} {name_match.group(2)}".strip()

    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", tex_content)
    if email_match:
        cv_data["basics"]["email"] = email_match.group(0)

    phone_match = re.search(r"\+?\d[\d\s\-]{8,15}\d", tex_content)
    if phone_match:
        cv_data["basics"]["phone"] = phone_match.group(0).strip()

    # 2. Extract Sections (\section{Work Experience}, \section{Skills}, etc.)
    # Fixed escape for \end{document} -> \\end\{document\}
    section_pattern = r"\\section\*?\{([^\}]*)\}(.*?)(?=\\section\*?\{|\\end\{document\}|$)"
    sections = re.findall(section_pattern, tex_content, re.DOTALL | re.IGNORECASE)

    for sec_name, sec_body in sections:
        sec_name_clean = sec_name.lower().strip()

        # Handle Skills section
        if "skill" in sec_name_clean or "expertise" in sec_name_clean:
            items = re.findall(r"\\item\s+([^\n\\]+)", sec_body)
            if not items:
                raw_text = strip_latex_formatting(sec_body)
                items = [s.strip() for s in raw_text.split(",") if s.strip()]
            else:
                items = [strip_latex_formatting(i) for i in items]
            cv_data["skills"].extend(items)

        # Handle Experience section
        elif "experience" in sec_name_clean or "history" in sec_name_clean or "employment" in sec_name_clean:
            role_blocks = re.split(r"\\cventry|\\subsection\*?", sec_body)
            for block in role_blocks:
                if not block.strip():
                    continue

                highlights = re.findall(r"\\item\s+(.*?)(?=\\item|\\end\{itemize\}|\\\\|$)", block, re.DOTALL)
                clean_highlights = [strip_latex_formatting(h) for h in highlights if h.strip()]

                clean_block_text = strip_latex_formatting(block)
                lines = [line.strip() for line in clean_block_text.split("\n") if line.strip()]

                if lines:
                    cv_data["experience"].append({
                        "role_info": lines[0] if lines else "",
                        "highlights": clean_highlights if clean_highlights else lines[1:],
                    })

        # Handle Summary / Profile
        elif "summary" in sec_name_clean or "profile" in sec_name_clean or "about" in sec_name_clean:
            cv_data["summary"] = strip_latex_formatting(sec_body)

        # Handle Education section
        elif "education" in sec_name_clean:
            clean_edu = strip_latex_formatting(sec_body)
            edu_lines = [line.strip() for line in clean_edu.split("\n") if line.strip()]
            for line in edu_lines:
                cv_data["education"].append({"details": line})

    return cv_data


def main():
    parser = argparse.ArgumentParser(
        description="Extract structured JSON data from a raw LaTeX CV source file.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""Examples:
  python3 scripts/extract_cv_to_json.py
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
        help=f"Path to save destination JSON file (default: '{DEFAULT_OUTPUT_JSON}')",
    )

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"❌ Input file '{args.input}' not found.\n")
        parser.print_help()
        sys.exit(1)

    print(f"📖 Reading LaTeX CV from '{args.input}'...")
    with open(args.input, "r", encoding="utf-8") as f:
        tex_content = f.read()

    print("⚡ Parsing LaTeX structure...")
    cv_data = parse_latex_cv(tex_content)

    # Create destination directory if it doesn't exist
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    print(f"💾 Writing output to '{args.output}'...")
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(cv_data, f, indent=2, ensure_ascii=False)

    print(f"✅ Success! Generated '{args.output}'.")


if __name__ == "__main__":
    main()
