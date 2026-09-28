# ADR-001: SQLite Job Storage and Deduplication Mechanism

* **Status:** Accepted
* **Date:** 2026-01-15

## Context
The JobMatch pipeline processes job listings gathered from external job boards. To avoid re-evaluating previously processed jobs, wasting LLM tokens, or generating redundant cover letters, we needed a fast, persistent, and low-overhead storage solution that could enforce strict job deduplication.

## Decision
We adopted **SQLite** managed via `db.py` as the local database store (`jobs.db`) with a two-tiered deduplication strategy:

1. **Exact ID Match:** Checks if the platform-specific `job_id` (e.g., LinkedIn job ID) already exists in the `job_listings` table.
2. **Canonical Hash Normalization:** Generates a SHA-256 hash based on normalized strings of the company name and job title (stripping special characters, lowercasing, and standardizing common seniority terms like "Sr" to "Senior").
3. **Lookback Window:** Evaluates canonical hash duplicates within a configurable lookback window (default: 30 days) to allow re-evaluating positions if reposted after extended periods.

## Consequences
* **Positive:** Eliminates duplicate LLM calls and redundant report entries across multiple scraper runs.
* **Positive:** Zero infrastructure overhead—runs as a self-contained single file database (`jobs.db`).
* **Negative:** Local SQLite instances require file-level locking, which limits concurrent multi-threaded writes if the pipeline expands beyond single-process CLI runs.
