# ADR-003: Multi-Profile Track Matching Strategy

* **Status:** Accepted
* **Date:** 2026-03-05

## Context
Candidates often target multiple career trajectories (e.g., Senior Developer vs. Engineering Manager). Evaluating jobs against a single static resume leads to sub-optimal match scores and generic cover letters that fail to highlight track-specific achievements.

## Decision
We structured candidate profiles into separate JSON configuration files within a `profiles/` directory:

1. **Track Configuration:** Each JSON file represents a distinct professional focus (e.g., `developer.json`, `management.json`).
2. **Competitive Multi-Track Evaluation:** During pipeline execution (`main.py`), every unprocessed job is evaluated against *all* loaded profile tracks.
3. **Best Match Selection:** The pipeline selects the profile track returning the highest `fit_score`. If that score exceeds the minimum threshold (`--min-score`, default: 70), a tailored PDF cover letter is compiled using that track's specific context.

## Consequences
* **Positive:** Maximizes job fit accuracy and tailors output cover letters to the specific role type automatically.
* **Positive:** Adding a new career track requires only adding a new `.json` file to `profiles/` without altering core pipeline code.
* **Negative:** Increases total LLM invocation calls linearly ($N \times M$, where $N$ is unprocessed jobs and $M$ is profile tracks).
