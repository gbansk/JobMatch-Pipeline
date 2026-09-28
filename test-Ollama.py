import requests
from jobspy import scrape_jobs

print("=== STEP 1 VERIFICATION ===")

# 1. Test Ollama REST API
try:
    print("\n1. Testing Ollama local endpoint...")
    res = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": "llama3.2", "prompt": "Reply with 'Ollama Ready'", "stream": False},
        timeout=10
    )
    if res.status_code == 200 and "Ollama Ready" in res.json().get("response", ""):
        print("   ✅ Ollama + Llama 3.2: WORKING")
    else:
        print("   ❌ Ollama test failed:", res.text)
except Exception as e:
    print(f"   ❌ Could not connect to Ollama: {e}")

# 2. Test JobSpy Ingestion (LinkedIn)
try:
    print("\n2. Testing JobSpy scraper against LinkedIn...")
    jobs = scrape_jobs(
        site_name=["linkedin"],
        search_term="Software Engineer",
        location="Melbourne, Australia",
        results_wanted=2,
        country_indeed='Australia'
    )
    print(f"   ✅ JobSpy Scraper: WORKING (Fetched {len(jobs)} test jobs)")
except Exception as e:
    print(f"   ❌ JobSpy test failed: {e}")

print("\n===========================")
