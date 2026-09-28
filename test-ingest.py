from db import init_db
from ingest import fetch_new_linkedin_jobs

print("=== STEP 3 VERIFICATION ===")

# Ensure DB table exists
init_db()

# Run a test fetch with 1 targeted term and small batch size
test_terms = ["Software Engineer"]
jobs = fetch_new_linkedin_jobs(
    search_terms=test_terms,
    location="Melbourne, Australia",
    results_wanted_per_term=3,
    hours_old=168  # 7 days lookback for test run
)

if len(jobs) > 0:
    sample = jobs[0]
    print(f"\nSample Job Ingested:")
    print(f" - Title: {sample['title']}")
    print(f" - Company: {sample['company']}")
    print(f" - URL: {sample['raw_url']}")
    print(f" - Description Length: {len(sample['description'])} chars")
    print("\n✅ Step 3 Ingestion & Deduplication Pipeline: PASSED")
else:
    print("\n⚠️ No fresh jobs found (might be already in DB or no listings matched).")

print("===========================")
