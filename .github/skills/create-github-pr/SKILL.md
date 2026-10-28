---
name: create-github-pr
description: Create a GitHub pull request for the current branch after feature work is complete. Use when asked to open, create, or prepare a pull request.
---

# Create GitHub Pull Request

Create a pull request only after the requested work is complete. Use the `gh`
CLI for GitHub operations.

## Preflight checks

1. Inspect `git status --short`, the current branch, its upstream, and the diff
   against the intended base branch.
2. Do not include unrelated, untracked, generated, secret, or local-state
   files.
3. Confirm the branch is pushed. If it is not, push it with upstream tracking.
4. Run the smallest relevant validation for the changed code unless it has
   already passed and no further code changed.
5. Do not commit, amend, rebase, force-push, or merge unless explicitly asked.

## Pull request content

1. Use the repository's PR template if one exists.
2. Choose a concise, imperative title that describes the user-facing change.
3. Write a body with these sections when applicable:
   - `## Summary`: one to three concrete changes.
   - `## Validation`: exact commands run and their outcomes.
   - `## Risks / follow-up`: only real limitations, migrations, rollout notes,
     or intentionally deferred work.
4. Link relevant issues using GitHub closing keywords only when the user has
   identified an issue and closing it is intended.
5. Set the intended base branch; default to the repository default branch when
   no base is specified.

## Create and report

1. Create the PR using `gh pr create` with the prepared title, body, head, and
   base branch.
2. Do not merge the PR or request reviewers unless explicitly asked.
3. Report the PR URL, number, title, base branch, head branch, changed files,
   and validation status.
