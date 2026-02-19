---
name: review
description: Assume the reviewer role defined in `.claude/profiles/reviewer.md` and review the uncommitted code.
---

1. Run `git diff HEAD` and `git status` to identify all uncommitted changes (staged and unstaged).
2. Read the changed files to understand what was modified.
3. Follow the reviewer workflow in `.claude/profiles/reviewer.md` — check tests first, then implementation.
4. Run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy app/` and include any tool findings in your feedback.
5. Write all findings to `comments.md`, following the format specified in the reviewer profile.
6. Do not make any code changes yourself.
