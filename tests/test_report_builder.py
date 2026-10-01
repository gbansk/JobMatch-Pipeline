import json
import pytest
from pathlib import Path
from unittest.mock import patch

from report_builder import generate_html_report


@pytest.fixture
def sample_report_data():
    return {
        "timestamp": "2026-09-21 22:40",
        "jobs": [
            {
                "company": "CoStar Group",
                "title": "Software Engineer - Homepass",
                "location": "Cremorne, Victoria, Australia",
                "track": "Developer CV",
                "score": 92,
                "summary": "Strong engineering profile match with microservices background.",
                "key_alignments": [
                    "High proficiency in full-stack backend development.",
                    "Direct domain expertise in distributed system design."
                ],
                "missing_skills": [
                    "Experience with Kubernetes deployment pipelines."
                ],
                "job_url": "https://www.linkedin.com/jobs/view/4469261479",
                "pdf_filename": "CoverLetter_CoStarGroup_SoftwareEngineerHomepass.pdf"
            },
            {
                "company": "Acme Corp",
                "title": "Senior Go Engineer",
                "location": "Melbourne",
                "track": "Management CV",
                "score": 55,
                "summary": "Moderate match.",
                "key_alignments": [],
                "missing_skills": [
                    "Strong AWS Cloud Architecture certified track record."
                ],
                "job_url": "https://example.com/job",
                "pdf_filename": ""
            }
        ]
    }


@pytest.fixture
def sample_html_template(tmp_path):
    template_content = """
    <html>
    <body>
        <h1>Digest {{ timestamp }}</h1>
        {% for job in jobs %}
        <div class="card {% if job.score >= 80 %}high{% else %}low{% endif %}">
            <h2>{{ job.title }}</h2>

            {% if job.key_alignments %}
            <div class="alignments">
                <h3>Key Alignments</h3>
                <ul>
                {% for item in job.key_alignments %}
                    <li class="align-item">{{ item }}</li>
                {% endfor %}
                </ul>
            </div>
            {% endif %}

            {% if job.missing_skills %}
            <div class="gaps">
                <h3>Missing Skills</h3>
                <ul>
                {% for item in job.missing_skills %}
                    <li class="gap-item">{{ item }}</li>
                {% endfor %}
                </ul>
            </div>
            {% endif %}

            <a href="{{ job.job_url }}">Job Link</a>
            {% if job.pdf_filename %}
            <a href="{{ job.pdf_filename }}">PDF Link</a>
            {% endif %}
        </div>
        {% endfor %}
    </body>
    </html>
    """
    template_file = tmp_path / "report_template.html"
    template_file.write_text(template_content, encoding="utf-8")
    return template_file


def test_generate_html_report_success(tmp_path, sample_report_data, sample_html_template):
    """Test successful HTML report compilation using Jinja2 and JSON input."""
    data_file = tmp_path / "report_data.json"
    data_file.write_text(json.dumps(sample_report_data), encoding="utf-8")

    output_html = tmp_path / "output" / "match_report.html"

    # Execute generation using relative paths resolved against tmp_path
    generate_html_report(
        data_path=str(data_file),
        template_path=str(sample_html_template),
        output_path=str(output_html)
    )

    assert output_html.exists()
    content = output_html.read_text(encoding="utf-8")

    # Assert basic metadata content rendered correctly
    assert "Digest 2026-09-21 22:40" in content
    assert "Software Engineer - Homepass" in content
    assert "CoverLetter_CoStarGroup_SoftwareEngineerHomepass.pdf" in content
    assert "high" in content
    assert "low" in content

    # Assert key alignments are rendered
    assert "Key Alignments" in content
    assert "High proficiency in full-stack backend development." in content
    assert "Direct domain expertise in distributed system design." in content

    # Assert missing skills/gaps are rendered
    assert "Missing Skills" in content
    assert "Experience with Kubernetes deployment pipelines." in content
    assert "Strong AWS Cloud Architecture certified track record." in content


def test_generate_html_report_missing_data_file(tmp_path, sample_html_template):
    """Ensure FileNotFoundError is raised cleanly when report_data.json is missing."""
    non_existent_data = tmp_path / "missing_data.json"
    output_html = tmp_path / "match_report.html"

    with pytest.raises(FileNotFoundError):
        generate_html_report(
            data_path=str(non_existent_data),
            template_path=str(sample_html_template),
            output_path=str(output_html)
        )


def test_generate_html_report_creates_output_directory(tmp_path, sample_report_data, sample_html_template):
    """Ensure parent output directories are automatically created if they don't exist."""
    data_file = tmp_path / "report_data.json"
    data_file.write_text(json.dumps(sample_report_data), encoding="utf-8")

    # Deeply nested path that doesn't exist yet
    nested_output_html = tmp_path / "nested" / "docs" / "match_report.html"

    generate_html_report(
        data_path=str(data_file),
        template_path=str(sample_html_template),
        output_path=str(nested_output_html)
    )

    assert nested_output_html.exists()


def test_generate_html_report_normalizes_pdf_path(tmp_path):
    # 1. Setup temporary directory structure and dummy inputs
    data_file = tmp_path / "report_data.json"
    output_file = tmp_path / "match_report.html"
    
    # Mock data layout matching real application output
    mock_data = {
        "timestamp": "2026-10-01 10:00",
        "jobs": [
            {
                "company": "TestCorp",
                "title": "Software Engineer",
                "location": "Melbourne",
                "track": "Developer CV",
                "score": 85,
                "summary": "Great match",
                "key_alignments": [],
                "missing_skills": [],
                "job_url": "https://example.com/job/1",
                "pdf_filename": "CoverLetter_TestCorp_SoftwareEngineer.pdf"
            }
        ]
    }
    
    # Write mock JSON
    data_file.write_text(json.dumps(mock_data), encoding="utf-8")

    # 2. Execute report builder with relative project template
    generate_html_report(
        data_path=str(data_file),
        template_path="report_template.html",
        output_path=str(output_file)
    )

    # 3. Assert HTML output was generated and contains corrected path
    assert output_file.exists()
    html_content = output_file.read_text(encoding="utf-8")
    
    # Verify the href contains the 'pdfs/' prefix
    expected_href = 'href="pdfs/CoverLetter_TestCorp_SoftwareEngineer.pdf"'
    assert expected_href in html_content, f"Expected '{expected_href}' to be present in rendered HTML."