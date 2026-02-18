# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Python project for parsing invoices. Currently in initial setup — no source code, build system, or package manager has been configured yet.

The `.gitignore` includes entries for Ruff, mypy, pytest, and common Python virtual environment tools (uv, Poetry, PDM, Pipenv, Pixi), but none have been configured yet.

## Setup

Once a package manager and build system are chosen, update this file with:
- How to install dependencies
- How to run the project
- How to run tests (including a single test)
- How to lint and type-check

## Way of Working

### TDD cycle — Red → Green → Refactor

Follow strict TDD. Never write implementation code without a failing test first.

**Red**
- Write a test that describes the desired behaviour.
- Run it and confirm it fails for the right reason (not due to an import error or unrelated issue).
- Test names must read as behaviour descriptions: `test_returns_null_when_date_cannot_be_parsed`, not `test_date`.

**Green**
- Write the minimum code required to make the test pass — no more.
- Include correct type annotations from the start. `mypy --strict` must pass before moving on.
- Do not over-engineer during this phase; save design improvements for refactor.

**Refactor**
- With tests green, improve the code: clarity, naming, structure, duplication.
- Prioritise readability. Code is read far more than it is written.
- Do not change behaviour during refactor. Tests must remain green throughout.
- Ensure test coverage is meaningful: cover edge cases, error paths, and boundary conditions — not just the happy path.

Repeat the cycle for each small unit of behaviour.

### Code quality

- Linting and formatting rules (Ruff) apply from the first line of code. Do not defer linting fixes.
- All code must pass `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy app/` before committing.
- Mock at system boundaries (external I/O, the LLM model, filesystem). Prefer real objects for internal logic.
- Never commit failing tests or code that does not pass linting and type checking.

### Committing

- Commit after each completed refactor phase, not during red or green.
- Run the full test suite before committing to catch regressions.
- Always stop and ask for confirmation before creating a commit.
- Use conventional commit messages:
  - `feat:` — new behaviour
  - `fix:` — bug fix
  - `test:` — adding or updating tests
  - `refactor:` — structural improvements with no behaviour change
  - `chore:` — tooling, config, dependencies
