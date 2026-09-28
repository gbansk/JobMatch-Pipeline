# ADR-002: Local LLM Evaluation via Ollama and Automated LaTeX/PDF Rendering

* **Status:** Accepted
* **Date:** 2026-02-10

## Context
Job evaluation requires analyzing unformatted job descriptions against candidate profiles, outputting a fit score (0–100), generating tailored cover letter content, and compiling a polished PDF artifact. We required a solution that runs locally without API costs or data privacy concerns.

## Decision
We implemented a two-stage evaluation and compilation engine in `evaluator.py`:

1. **Local LLM Execution:** Uses local `ollama` CLI subprocess invocation (defaulting to `llama3.2`) to evaluate job descriptions against candidate CV JSON structures.
2. **Strict Output Parsing:** Forces LLM responses into a structured format starting with `FIT_SCORE: <number>` followed by cover letter body paragraphs.
3. **Automated TeX Templating & Compilation:** Substitutes generated cover letter body text into a LaTeX template (`cover_letter_template.tex`) and compiles it directly to PDF via `pdflatex`.

## Consequences
* **Positive:** 100% offline, privacy-preserving, and free from external API rate limits or recurring costs.
* **Positive:** Generates high-quality, professionally formatted PDF cover letters automatically.
* **Negative:** Requires local dependencies (`ollama` daemon with pre-pulled models and a local TeX distribution like TeX Live / MacTeX).
