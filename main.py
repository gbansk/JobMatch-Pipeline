#!/usr/bin/env python3
"""
Full JobMatch Pipeline:
1. Scrapes jobs from LinkedIn using python-jobspy into SQLite (`jobs.db`).
2. Deduplicates listings via db.py (is_duplicate & save_job).
3. Processes pending jobs against multiple profile JSON configurations (e.g. profiles/*.json).
4. Evaluates match score, compiles LaTeX/PDF cover letters, emits report_data.json, and generates an HTML summary report.
"""

import argparse
from datetime import datetime
import glob
import json
import os
import sys
from pathlib import Path

# Import local pipeline modules
from db import (
    init_db,
    save_job,
    is_duplicate,
    get_unprocessed_jobs,
    update_job_status
)
from evaluator import evaluate_job
from cover_letter import render_latex_cover_letter
from report_builder import generate_html_report

try:
    from jobspy import scrape_jobs
    JOBSPY_AVAILABLE = True
except ImportError:
    JOBSPY_AVAILABLE = False


def load_profiles(profiles_dir: str = "profiles") -> list[dict]:
    """Loads all profile JSON configuration files from a directory, excluding templates."""
    profiles = []
    pattern = os.path.join(profiles_dir, "*.json")
    
    for filepath in glob.glob(pattern):
        filename = os.path.basename(filepath)
        
        # Skip template files or schema definitions
        if filename.lower() == "template.json":
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            profile_data = json.load(f)
            # Use filename without extension as track identifier
            track_name = os.path.splitext(filename)[0].capitalize() + " CV"
            profiles.append({
                "track": track_name,
                "data": profile_data,
                "file_path": filepath
            })
            
    if not profiles:
        raise FileNotFoundError(f"No profile JSON files found in directory: '{profiles_dir}'")
        
    return profiles


def run_linkedin_scraper(search_term: str, location: str, results_wanted: int = 15) -> int:
    """Scrapes LinkedIn listings and saves non-duplicate records to jobs.db."""
    if not JOBSPY_AVAILABLE:
        print("❌ Error: 'python-jobspy' is not installed. Run `pip install python-jobspy`.")
        sys.exit(1)

    print(f"🌐 Scraping LinkedIn for '{search_term}' in '{location}' (Target: {results_wanted})...")

    try:
        jobs_df = scrape_jobs(
            site_name=["linkedin"],
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            country_code="AU",
        )

        if jobs_df.empty:
            print("⚠️ No jobs returned from scraper.")
            return 0

        inserted_count = 0
        for _, row in jobs_df.iterrows():
            job_id = str(row.get("id", ""))
            company = str(row.get("company", "Unknown"))
            title = str(row.get("title", "Unknown"))

            # Check database for exact ID or title/company hash deduplication
            if not is_duplicate(job_id, company, title):
                save_job(
                    job_id=job_id,
                    platform="linkedin",
                    company=company,
                    title=title,
                    location=str(row.get("location", "")),
                    raw_url=str(row.get("job_url", "")),
                    summary=str(row.get("description", "")),
                )
                inserted_count += 1

        print(f"📥 Saved {inserted_count} new job(s) to SQLite database.")
        return inserted_count
    except Exception as e:
        print(f"❌ Scraper error: {e}")
        return 0


def run_pipeline(
    profiles_dir: str,
    model: str,
    template_path: str,
    output_dir: str,
    min_score: int = 70
):
    """Processes pending jobs against all profiles, picks the highest-scoring track, generates PDF cover letters, and builds HTML report."""
    pending_jobs = get_unprocessed_jobs()

    if not pending_jobs:
        print("✅ No pending/unprocessed jobs in database.")
        return

    profiles = load_profiles(profiles_dir)
    print(f"📋 Found {len(pending_jobs)} unprocessed job(s) in queue.")
    print(f"📁 Loaded {len(profiles)} profile track(s): {[p['track'] for p in profiles]}\n")

    os.makedirs(output_dir, exist_ok=True)
    evaluated_results = []

    for idx, job in enumerate(pending_jobs, 1):
        job_db_id = job.get("id")
        title = job.get("title", "Position")
        company = job.get("company", "Company")
        location = job.get("location", "")
        raw_url = job.get("raw_url", "#")
        description = job.get("description", "")

        print(f"\n--- [{idx}/{len(pending_jobs)}] Evaluating: '{title}' at '{company}' ---")

        # Create unique clean output file names
        safe_company = "".join(c for c in company if c.isalnum())
        safe_title = "".join(c for c in title if c.isalnum())
        pdf_dir = os.path.join(output_dir, "pdfs")
        os.makedirs(pdf_dir, exist_ok=True)
        output_tex = os.path.join(pdf_dir, f"CoverLetter_{safe_company}_{safe_title}.tex")
        output_pdf = os.path.join(pdf_dir, f"CoverLetter_{safe_company}_{safe_title}.pdf")

        best_score = -1
        best_body_text = ""
        best_profile = None
        best_alignments = []
        best_missing = []

        # Evaluate job against every profile track (e.g. Developer vs Management)
        for profile in profiles:
            try:
                body_text, fit_score, key_alignments, missing_skills = evaluate_job(
                    cv_path=profile["file_path"],
                    job_description=description,
                    model=model,
                    template_path=template_path,
                    output_tex=output_tex
                )

                print(f"   ↳ Track '{profile['track']}': {fit_score}/100")

                if fit_score > best_score:
                    best_score = fit_score
                    best_body_text = body_text
                    best_profile = profile
                    best_alignments = key_alignments
                    best_missing = missing_skills

            except Exception as e:
                print(f"❌ Error evaluating track '{profile['track']}' for job ID {job_db_id}: {e}")

        if best_profile is None:
            update_job_status(job_db_id, status="error")
            continue

        print(f"📊 Best Match Fit Score: {best_score}/100 ({best_profile['track']})")

        pdf_filename = ""
        if best_score >= min_score:
            status = "matched"
            render_latex_cover_letter(
                cv_data=best_profile["data"],
                body_text=best_body_text,
                template_path=template_path,
                output_tex=output_tex,
                company=company
            )
            print(f"✨ Match found! Cover letter saved to: {output_tex}")
            pdf_filename = os.path.basename(output_pdf)
        else:
            status = "skipped_low_score"
            print(f"⏩ Skipped (Score {best_score} below minimum threshold {min_score})")

        update_job_status(job_db_id, status=status, score=best_score)

        evaluated_results.append({
            "company": company,
            "title": title,
            "location": location,
            "track": best_profile["track"],
            "score": best_score,
            "summary": description[:250] + "..." if len(description) > 250 else description,
            "key_alignments": best_alignments,
            "missing_skills": best_missing,
            "job_url": raw_url,
            "pdf_filename": pdf_filename
        })

    if evaluated_results:
        # Prepare structured JSON report payload
        report_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "jobs": evaluated_results
        }

        json_out_path = os.path.join(output_dir, "report_data.json")
        html_out_path = os.path.join(output_dir, "match_report.html")

        # Save report_data.json
        with open(json_out_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        # Generate Jinja2 rendered HTML report
        generate_html_report(
            data_path=json_out_path,
            template_path="report_template.html",
            output_path=html_out_path
        )
        print(f"\n📊 Match Report generated: {html_out_path}")


def main():
    parser = argparse.ArgumentParser(description="End-to-end Job Match Pipeline using SQLite database.")
    parser.add_argument(
        "-s", "--search", default="Software Engineer", help="Search query/title for scraper"
    )
    parser.add_argument(
        "-l", "--location", default="Melbourne, Australia", help="Search location"
    )
    parser.add_argument(
        "-n", "--count", type=int, default=15, help="Number of jobs to scrape"
    )
    parser.add_argument(
        "-p", "--profiles", default="profiles", help="Path to directory containing profile JSON files"
    )
    parser.add_argument(
        "-m", "--model", default="llama3.2", help="Ollama model to use"
    )
    parser.add_argument(
        "-t", "--template", default="cover_letter_template.tex", help="LaTeX template path"
    )
    parser.add_argument(
        "-o", "--outdir", default="output", help="Directory to output generated files"
    )
    parser.add_argument(
        "--min-score", type=int, default=70, help="Minimum fit score threshold (0-100) to render cover letter"
    )
    parser.add_argument(
        "--skip-scrape", action="store_true", help="Skip scraping and process existing pending jobs in DB"
    )

    args = parser.parse_args()

    if not os.path.exists(args.profiles):
        print(f"❌ Profiles directory '{args.profiles}' not found.")
        sys.exit(1)

    print("🚀 Starting JobMatch Pipeline...")

    # Step 1: Initialize database schema
    init_db()

    # Step 2: Scrape jobs unless skipped
    if not args.skip_scrape:
        run_linkedin_scraper(
            search_term=args.search,
            location=args.location,
            results_wanted=args.count
        )

    # Step 3: Run pipeline for pending database records through multi-profile evaluator
    run_pipeline(
        profiles_dir=args.profiles,
        model=args.model,
        template_path=args.template,
        output_dir=args.outdir,
        min_score=args.min_score
    )

    print("\n🎉 Pipeline run complete!")


if __name__ == "__main__":
    main()
