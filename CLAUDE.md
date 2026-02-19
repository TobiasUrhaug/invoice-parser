# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Stateless HTTP service that extracts structured fields from PDF invoices using a local LLM. Built with Python 3.12, FastAPI, pdfplumber, PaddleOCR, and llama-cpp-python. Managed with uv.

## Setup

Install dependencies:

```bash
uv sync
```

Run the service locally:

```bash
uv run uvicorn app.main:app --reload
```

Run all tests:

```bash
uv run pytest
```

Run fast tests only (skips integration tests that load the real model):

```bash
uv run pytest -m "not integration"
```

Run a single test:

```bash
uv run pytest tests/test_validator.py::test_valid_dict_produces_correct_invoice_result
```

Lint and type-check:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app/
```

Environment variables are documented in `.env.example`. `API_KEY` is required.

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
