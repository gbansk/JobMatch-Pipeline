---
name: review-python-work
description: Validate and prepare completed Python feature work for handoff. Use after implementing a feature and before considering it complete.
---

# Review Python Work

Run this skill after implementing a feature. Make the smallest changes needed
to address any issue found; do not broaden scope or alter unrelated work.

## Confirm the outcome

- Restate the feature's observable acceptance criteria from the request.
- Inspect the changed code and affected call paths.
- Verify normal, boundary, and failure behavior.
- Ensure errors are explicit, actionable, and consistent with existing project
  patterns.

## Preserve design quality

- Prefer existing project patterns, abstractions, and helpers over new ones.
- Remove duplication only when the shared abstraction is clearer than the
  repeated code.
- Apply SOLID pragmatically: maintain single-purpose units, dependency
  boundaries, and testable interfaces; do not introduce abstractions solely to
  satisfy a principle.
- Keep public APIs, configuration, and data formats backward compatible unless
  the feature explicitly changes them.

## Python-specific checks

- Add or update focused tests for new behavior and important edge cases.
- Run the narrowest relevant test suite, then project-standard linting,
  formatting, and type checking where configured.
- Check type hints on new or changed public functions and models.
- Avoid mutable default arguments, broad exception handling, hidden global
  state, and resource leaks.
- Use context managers for files, connections, and other managed resources.

## Security and operational checks

- Validate untrusted input at system boundaries.
- Do not expose secrets, tokens, personal data, or sensitive implementation
  details in logs or errors.
- Verify authorization is enforced wherever the feature reads or changes
  protected data.
- Consider performance for expected data volume and failure recovery for
  external I/O.
- Update migrations, configuration examples, documentation, and release notes
  only when the feature requires them.

## Review the change

- Inspect the diff for accidental edits, dead code, debugging output, and
  generated artifacts.
- Do not revert or modify unrelated existing work in a dirty worktree.
- Report changed files, behavior verified, commands run and results, and any
  remaining risk or follow-up.

## Completion standard

Mark the feature complete only when its acceptance criteria are demonstrated,
relevant checks pass, and the diff contains no unrelated changes.
