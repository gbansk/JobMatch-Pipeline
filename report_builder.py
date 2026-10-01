import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

BASE_DIR = Path(__file__).resolve().parent

def generate_html_report(data_path="output/report_data.json", 
                         template_path="report_template.html", 
                         output_path="output/match_report.html"):
    
    # Resolve paths relative to BASE_DIR if they are relative
    abs_data_path = Path(data_path) if Path(data_path).is_absolute() else BASE_DIR / data_path
    abs_template_path = Path(template_path) if Path(template_path).is_absolute() else BASE_DIR / template_path
    abs_output_path = Path(output_path) if Path(output_path).is_absolute() else BASE_DIR / output_path

    # Ensure output directory exists
    abs_output_path.parent.mkdir(parents=True, exist_ok=True)

    # Read JSON payload
    with open(abs_data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Get the list of items from 'jobs' OR 'matches'
    items = data.get("jobs") or data.get("matches") or []

    # 2. Loop through each job/match
    for item in items:
        # Look for 'pdf_filename', 'cover_letter_pdf', or 'pdf_path' on the item
        raw_pdf = item.get("pdf_filename") or item.get("cover_letter_pdf") or item.get("pdf_path")
        
        # Treat '#' as a sentinel for "no PDF" (used by test fixtures)
        if raw_pdf and raw_pdf != "#":
            filename = Path(raw_pdf).name
            formatted_path = f"pdfs/{filename}"

            # Assign back to all keys so Jinja finds it regardless of variable name
            item["pdf_filename"] = formatted_path
            item["cover_letter_pdf"] = formatted_path
            item["pdf_path"] = formatted_path

    # Configure Jinja2 loader to search in template's parent directory
    template_dir = abs_template_path.parent
    template_name = abs_template_path.name

    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(template_name)
    rendered_html = template.render(**data)

    # Write output HTML
    with open(abs_output_path, "w", encoding="utf-8") as f:
        f.write(rendered_html)

if __name__ == "__main__":
    generate_html_report()
