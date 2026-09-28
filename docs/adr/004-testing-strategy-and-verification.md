# ADR-004: Automated Unit & Integration Testing Strategy for Pipeline Reliability

* **Status:** Accepted
* **Date:** 2026-09-21

## Context
As the JobMatch Pipeline evolved to handle multi-profile CV tracks, deduplication logic, local LLM evaluation via Ollama, and automated LaTeX/PDF generation, maintaining system reliability became critical. Previously, verification was done manually via inline checks and standalone scripts (`ingest.py`, `test_ollama.py`), which led to environment-dependent test failures, lack of isolation, and potential regressions when modifying core pipeline logic.

We needed a standardized, repeatable testing framework that:
1. Validates SQLite database isolation and deduplication logic without polluting production data (`jobs.db`).
2. Mocks external boundaries (Ollama CLI subprocess calls and `python-jobspy` scraping) for deterministic execution.
3. Cleans up intermediate build artifacts (`.aux`, `.log`, `.out`) from LaTeX cover letter generation.
4. Excludes schema template files (`template.json`) from candidate profile matching.
5. Measures test coverage metrics automatically via `pytest-cov`.

## Decision
We adopted **Pytest** with **pytest-cov** as our official testing framework and restructured the codebase to decouple testing from production execution.

### Key Implementation Choices:

1. **Test Directory Layout & Package Resolution:**
   * Moved all unit test files to a dedicated `tests/` directory (`tests/test_db.py`, `tests/test_evaluator.py`, `tests/test_main.py`).
   * Configured `tests/conftest.py` to automatically inject the project root into `sys.path`, preventing module import failures across execution environments.

2. **Isolated Database Testing (`test_db.py`):**
   * Replaced top-level procedural assertions with `pytest` fixtures (`mock_db` using `tmp_path` and `monkeypatch`).
   * Each test executes against an in-memory or ephemeral SQLite database instance, ensuring tests never interact with or pollute the live `jobs.db`.

3. **LLM Evaluation & LaTeX Compilation Isolation (`test_evaluator.py`):**
   * Mocked `subprocess.run` calls to simulate Ollama CLI responses without requiring a running daemon during test runs.
   * Parameterized tests for fit score parsing (`FIT_SCORE: <number>`) to cover formatting edge cases, missing scores, and non-numeric defaults.
   * Added explicit cleanup logic in `render_latex_cover_letter` (`finally` block) to remove intermediate build artifacts (`.aux`, `.log`, `.out`, etc.) while preserving target `.tex` and `.pdf` output.

4. **Pipeline Orchestration & Profile Handling (`test_main.py`):**
   * Mocked `python-jobspy` scraping to test deduplication integration without executing live network queries.
   * Explicitly added filtering in `load_profiles()` to ignore `template.json` while loading valid profile tracks (`*.json`).
   * Verified multi-track evaluation logic to ensure the highest-scoring CV profile is selected for cover letter generation.

5. **Retention of Diagnostic Scripts:**
   * Retained `test_ollama.py` as a standalone diagnostic smoke-test script (or isolated via `pytest.ini` / moved to `scripts/`) to allow rapid manual verification of local Ollama daemon health outside automated CI test runs.

## Consequences

### Positive
* **Deterministic Test Execution:** Unit tests execute in under a second without requiring live external dependencies (Ollama, LinkedIn scraping, or system `pdflatex`).
* **Clean Workspaces:** Intermediate build artifacts are cleaned up automatically post-compilation.
* **Regression Safety:** Full coverage across `db.py`, `evaluator.py`, and `main.py` guarantees early detection of breaking changes during refactoring.
* **Measurable Quality:** Execution via `pytest --cov=. --cov-report=term-missing` provides clear visibility into untested code paths.

### Operational Command Summary
* **Run Test Suite:** `pytest -v`
* **Check Coverage Summary:** `pytest --cov=. --cov-report=term-missing`
* **Generate Line-by-Line HTML Report:** `pytest --cov=. --cov-report=html`
