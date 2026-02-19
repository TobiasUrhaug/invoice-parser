# Invoice Parsing Service — Implementation Tasks (MVP)

**Reference:** spec.md, requirements.md
**Stack:** Python 3.12, FastAPI, uv, pdfplumber, PaddleOCR, llama-cpp-python, Docker, Hugging Face Spaces

Tasks are grouped by phase. Each phase should be completed before the next begins. Within a phase, tasks with no dependency listed can be worked in parallel.

---

## Phase 0 — Project Setup

### [x] T-01 — Initialise Python project with uv

**Description:**
Initialise the project using uv. Create `pyproject.toml` with project metadata, Python version pin (`>=3.12`), and initial dependency groups (main, dev).

**Acceptance criteria:**
- `uv sync` installs without errors
- `pyproject.toml` has `[project]`, `[dependency-groups]` (dev group for test/lint tools), and `[tool.ruff]` / `[tool.mypy]` sections
- A `uv.lock` file is committed

**Dependencies:** None

---

### [x] T-02 — Configure linting and type checking

**Description:**
Configure Ruff (linting + formatting) and mypy (strict type checking) in `pyproject.toml`. Add both to the dev dependency group.

**Ruff rules to enable:** `E`, `F`, `I` (isort), `UP` (pyupgrade).
**mypy settings:** `strict = true`, `python_version = "3.12"`.

**Acceptance criteria:**
- `uv run ruff check .` passes on a clean project
- `uv run ruff format --check .` passes
- `uv run mypy app/` passes on a minimal `app/` with a typed stub

**Dependencies:** T-01

---

### [x] T-03 — Configure pytest

**Description:**
Add pytest and httpx (for async FastAPI test client) to the dev dependency group. Create `tests/` directory with a `conftest.py` stub.

**Acceptance criteria:**
- `uv run pytest` runs and exits 0 on an empty test suite
- `pyproject.toml` has a `[tool.pytest.ini_options]` section with `testpaths = ["tests"]`

**Dependencies:** T-01

---

### [x] T-04 — Create FastAPI application skeleton

**Description:**
Create `app/main.py` with a FastAPI app instance and a lifespan handler (for model loading in a later phase). Create `app/api/v1/router.py` with placeholder route stubs. Register the v1 router under the `/api/v1` prefix.

Create `app/core/config.py` using `pydantic-settings`. Load all environment variables defined in spec.md section 9 (Environment Variables). Add `pydantic-settings` to main dependencies.

**Acceptance criteria:**
- `uv run uvicorn app.main:app --reload` starts without errors
- `GET /health` returns `{"status": "ok", "model_loaded": false}` (model not yet integrated)
- All config values are loaded from environment variables; missing required vars (`API_KEY`) cause startup to fail with a clear error

**Dependencies:** T-01

---

### [x] T-05 — Create Dockerfile

**Description:**
Write a `Dockerfile` targeting Hugging Face Spaces (port 7860). Use `python:3.12-slim` as base. Install system dependencies: `poppler-utils` (for pdf2image), `libgomp1` (required by PaddleOCR). Use uv to install production dependencies only (`--no-dev`). Copy app source. Set `CMD` to run uvicorn.

Create a `.dockerignore` to exclude `tests/`, `*.md`, `__pycache__`, `.env*`, and model files.

Create a `.env.example` documenting all environment variables with placeholder values.

**Acceptance criteria:**
- `docker build -t invoice-parser .` succeeds
- `docker run -e API_KEY=test -p 7860:7860 invoice-parser` starts and `GET /health` responds

**Dependencies:** T-04

---

## Phase 1 — PDF Extraction Layer

### [x] T-06 — Implement text PDF extractor (pdfplumber fast path)

**Description:**
Create `app/services/pdf_extractor.py`. Define an abstract base class `PDFExtractor` with a single abstract method:

```python
def extract_text(self, file_bytes: bytes) -> str: ...
```

Implement `PlumberExtractor(PDFExtractor)` using pdfplumber. Extract text page by page, join with double newlines. Return the combined string. Add `pdfplumber` to main dependencies.

**Acceptance criteria:**
- Unit test with a real text-based PDF fixture returns a non-empty string containing expected content
- Unit test with zero-byte input raises `ValueError`
- mypy passes

**Dependencies:** T-01, T-03

---

### [x] T-07 — Implement scanned PDF detection and OCR fallback

**Description:**
In `pdf_extractor.py`, implement:

1. `_is_text_based(text: str, page_count: int) -> bool`: Returns `True` if `len(text) / page_count >= MIN_TEXT_CHARS_PER_PAGE` (from config).

2. `PaddleOCRExtractor(PDFExtractor)`: Converts PDF pages to images using `pdf2image`, runs PaddleOCR on each image, concatenates the recognised text. Add `paddleocr`, `pdf2image`, and `Pillow` to main dependencies.

3. `SmartPDFExtractor(PDFExtractor)`: Wraps both extractors. Tries pdfplumber first; if `_is_text_based` returns `False`, delegates to `PaddleOCRExtractor`. Returns both the text and the path taken (`"text"` or `"ocr"`).

Update `app/services/pipeline.py` (stub) to use `SmartPDFExtractor`.

**Acceptance criteria:**
- Unit test: a scanned PDF fixture triggers the OCR path
- Unit test: a digital PDF fixture uses the pdfplumber path
- The returned `extraction_path` value is `"text"` or `"ocr"` accordingly
- mypy passes

**Dependencies:** T-06

---

### [x] T-08 — Implement PDF input validation

**Description:**
In `app/api/v1/router.py`, add input validation before handing the file to the pipeline:

1. **Size check:** Reject files larger than `MAX_FILE_SIZE_MB`. Return `413`.
2. **MIME type check:** Reject files where the uploaded `content_type` is not `application/pdf`. Return `400`.
3. **Magic bytes check:** Read the first 4 bytes of the file and verify they match the PDF magic number (`%PDF`). Return `400` if they do not. This guards against misnamed files.

**Acceptance criteria:**
- Unit test: uploading a PNG file returns `400`
- Unit test: uploading a file > 10 MB returns `413`
- Unit test: uploading a `.pdf` file with non-PDF content returns `400`
- Valid PDF passes all checks

**Dependencies:** T-04

---

## Phase 2 — LLM Extraction Layer

### [x] T-09 — Model download and loading

**Description:**
Create `app/services/llm_extractor.py`. Implement model initialisation:

1. On application startup (FastAPI lifespan handler in `main.py`), check if the GGUF file exists at `MODEL_DIR / MODEL_FILENAME`.
2. If not present, download it from Hugging Face Hub using the `huggingface-hub` library (`hf_hub_download`). Add `huggingface-hub` and `llama-cpp-python` to main dependencies.
3. Load the model with `Llama(model_path=..., n_ctx=4096, n_gpu_layers=0, verbose=False)`.
4. Store the loaded model instance in application state.
5. After loading, set `model_loaded = True` in app state so `/health` reflects it.
6. While loading, extraction requests should return `503`.

**Note:** `llama-cpp-python` must be installed with `CMAKE_ARGS="-DGGML_BLAS=OFF"` for pure CPU use. Document this in `pyproject.toml` or `README.md`.

**Acceptance criteria:**
- On cold start, the model downloads if absent (can be tested by pointing `MODEL_DIR` at an empty temp directory)
- After loading, `GET /health` returns `"model_loaded": true`
- While loading, `POST /api/v1/extract` returns `503`
- Model instance is reused across requests (not reloaded per request)

**Dependencies:** T-04

---

### [x] T-10 — Implement LLM field extraction

**Description:**
In `llm_extractor.py`, define `LLMExtractor` with method `extract_fields(text: str) -> dict`. Implement:

1. **System prompt:** Instruct the model to extract the five invoice fields from provided text, return only a JSON object, use ISO 8601 dates, represent monetary values as `{"amount": <number>, "currency": "<ISO4217>"}` or `null`, set undetectable fields to `null`, and handle any European language.
2. **User prompt:** The raw extracted text with a brief instruction prefix.
3. **Inference:** Call the model with `temperature=0`, `max_tokens=512`.
4. **Output parsing:** Parse the response with `json.loads`. On failure, use a regex to extract the first `{...}` block and retry. On continued failure, return a dict with all five keys set to `null`.

**The five keys:** `invoiceDate`, `invoiceReference`, `netAmount`, `vatAmount`, `totalAmount`.

**Acceptance criteria:**
- Unit test with synthetic invoice text returns a dict with all five keys present
- Unit test where the model output is malformed (simulated) still returns a dict with all five keys (as null)
- Keys are always present in the returned dict regardless of extraction outcome
- mypy passes

**Dependencies:** T-09

---

## Phase 3 — Validation Layer

### [x] T-11 — Define response schema

**Description:**
In `app/api/v1/schemas.py`, define Pydantic v2 models:

```python
class MonetaryAmount(BaseModel):
    amount: Decimal
    currency: str | None

class InvoiceResult(BaseModel):
    invoiceDate: date | None
    invoiceReference: str | None
    netAmount: MonetaryAmount | None
    vatAmount: MonetaryAmount | None
    totalAmount: MonetaryAmount | None
```

Use `Decimal` for amounts to avoid floating-point rounding issues.

**Acceptance criteria:**
- Model serialises to the JSON format shown in spec.md section 4.2
- `null` fields are present in serialised output (not omitted) — use `model_config = ConfigDict(populate_by_name=True)`
- mypy passes

**Dependencies:** T-04

---

### [x] T-12 — Implement validation and business rule checks

**Description:**
Create `app/services/validator.py`. Implement `InvoiceValidator` with method `validate(raw: dict) -> InvoiceResult`:

1. **Schema coercion:** Use `InvoiceResult.model_validate(raw)` with a try/except. Fields that fail type coercion are set to `null`.
2. **Date normalisation:** If `invoiceDate` comes in as a string that is not ISO 8601, attempt to parse it with `dateutil.parser.parse` and convert to `date`. Add `python-dateutil` to main dependencies.
3. **Totals consistency check:** If all three monetary fields are non-null, verify `|net + vat - total| / total <= 0.01`. If the check fails, log a warning (do not nullify or modify values).
4. **Negative amount check:** Log a warning if any `amount` is negative.

**Acceptance criteria:**
- Unit test: valid dict produces correct `InvoiceResult`
- Unit test: `invoiceDate` in format `"15. Januar 2024"` is normalised to `date(2024, 1, 15)`
- Unit test: totals inconsistency logs a warning but still returns all three values
- Unit test: field with wrong type (e.g. `invoiceDate: 12345`) is returned as `null`
- mypy passes

**Dependencies:** T-11

---

## Phase 4 — API Layer

### [x] T-13 — Implement authentication middleware

**Description:**
Create `app/core/security.py`. Implement a FastAPI dependency `verify_api_key(x_api_key: str = Header(...)) -> None` that compares the provided key against `settings.API_KEY` using `hmac.compare_digest` (constant-time). Raise `HTTPException(status_code=401)` on mismatch or missing header.

Apply this dependency globally to all routes under `/api/v1`.

**Acceptance criteria:**
- Request without `X-API-Key` returns `401`
- Request with wrong key returns `401`
- Request with correct key proceeds normally
- mypy passes

**Dependencies:** T-04

---

### [x] T-14 — Implement extraction endpoint

**Description:**
In `app/api/v1/router.py`, implement `POST /api/v1/extract`:

1. Validate input (T-08).
2. Read file bytes.
3. Call `pipeline.run(file_bytes)` which returns `(InvoiceResult, extraction_path)`.
4. Return the `InvoiceResult` as JSON.

Add structured logging before and after the pipeline call (see spec.md section 7 for log fields). Use `request_id` generated with `uuid.uuid4()`.

**Acceptance criteria:**
- End-to-end: uploading a real text PDF returns `200` with correct JSON structure
- All five keys are always present in the response
- Structured log line is emitted for each request with all fields from spec.md section 7
- mypy passes

**Dependencies:** T-07, T-10, T-12, T-13

---

### [x] T-15 — Implement structured logging

**Description:**
Create `app/core/logging.py`. Configure Python's `logging` module to emit JSON-formatted lines to stdout. Each log record for a request should include the fields from spec.md section 7. Use a custom `logging.Formatter` that serialises the record to JSON.

Configure the logger in the FastAPI lifespan handler. All application code should use `logging.getLogger(__name__)` and pass structured fields as `extra={}`.

**Acceptance criteria:**
- Running the service and making a request produces a single JSON log line to stdout
- The log line contains all required fields
- Log level is configurable via `LOG_LEVEL` environment variable (default: `INFO`)

**Dependencies:** T-04

---

### [x] T-16 — Implement global error handling

**Description:**
In `app/main.py`, register exception handlers for:

1. `RequestValidationError` → `422` with `{"error": "..."}` envelope
2. `HTTPException` → pass through with `{"error": exception.detail}`
3. Unhandled `Exception` → `500` with `{"error": "Internal processing failure"}` (do not leak stack traces to clients; log the full exception server-side)

**Acceptance criteria:**
- Uploading a non-PDF returns `{"error": "..."}` not FastAPI's default validation error shape
- Intentionally raising an unhandled exception in a route returns `500` with the correct envelope
- Stack traces are logged but not returned to the client

**Dependencies:** T-04

---

## Phase 5 — Integration Testing

### [ ] T-17 — Create PDF test fixtures

**Description:**
Collect or generate a small set of PDF invoices for use as test fixtures in `tests/fixtures/`. The set should include:

- At least one digital (text-based) PDF invoice in English
- At least one digital PDF invoice in a non-English European language (e.g. Norwegian or German)
- At least one scanned (image-based) PDF invoice
- At least one PDF with partial information missing (to test `null` field handling)

These should be real or realistic invoices (not actual client invoices — generate synthetic ones or use freely available samples). Commit them to the repository.

**Acceptance criteria:**
- Fixtures exist in `tests/fixtures/`
- Each fixture has a corresponding `.json` file with the expected extraction output (for regression testing)

**Dependencies:** None

---

### [ ] T-18 — Write unit tests for all service components

**Description:**
Write unit tests for each service module:

- `test_pdf_extractor.py`: Text path, OCR path selection, invalid input handling
- `test_llm_extractor.py`: Field key completeness, malformed LLM output handling (mock the model)
- `test_validator.py`: Schema coercion, date normalisation, totals consistency check, negative amount warning

Mock the LLM model in `test_llm_extractor.py` — do not load the actual model in unit tests.

**Acceptance criteria:**
- `uv run pytest tests/ -k "not integration"` passes with >80% coverage on service modules
- No test loads the actual LLM model

**Dependencies:** T-07, T-10, T-12, T-17

---

### [ ] T-19 — Write integration tests for the API

**Description:**
Write `test_api.py` using `httpx.AsyncClient` with the FastAPI test client. Tests should cover:

- `POST /api/v1/extract` with a valid PDF → `200` with correct schema
- `POST /api/v1/extract` with no API key → `401`
- `POST /api/v1/extract` with a non-PDF file → `400`
- `POST /api/v1/extract` with an oversized file → `413`
- `GET /health` → `200`

Mark integration tests with `@pytest.mark.integration`. These tests may load the real model and are expected to be slow.

**Pre-implementation notes:**

- **OCR fixture verification:** The expected values in `tests/fixtures/invoice_scanned.json` were not derived by running the actual pipeline — they were hand-authored when the fixture was generated. Before wiring `invoice_scanned.pdf` into integration tests, run the pipeline against the fixture and update `invoice_scanned.json` with the real output. OCR accuracy depends on font rendering and engine version; the current expected values may produce spurious failures.

- **Non-ASCII handling:** `tests/fixtures/invoice_german.pdf` is deliberately ASCII-only because the Helvetica Type1 font cannot render umlauts (ä, ö, ü, ß). It tests non-English language handling only. Consider sourcing a separately generated fixture (e.g. using a Unicode-capable font or a real German invoice PDF) to verify non-ASCII character handling end-to-end.

**Acceptance criteria:**
- All tests pass
- Integration tests are skippable via `-m "not integration"` for fast local runs

**Dependencies:** T-14, T-16, T-17

---

## Phase 6 — Deployment

### [ ] T-20 — Configure Hugging Face Spaces deployment

**Description:**
Create a `README.md` for the HF Space (HF Spaces uses the `README.md` YAML front matter for space configuration).

Add the YAML front matter block:
```yaml
---
title: Invoice Parser
emoji: 📄
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---
```

Document in the project `README.md`:
- How to install dependencies (`uv sync`)
- How to run the service locally (`uv run uvicorn app.main:app --reload`)
- How to run all tests (`uv run pytest`)
- How to run fast tests only (`uv run pytest -m "not integration"`)
- How to lint (`uv run ruff check .`)
- How to type-check (`uv run mypy app/`)
- Required environment variables (reference `.env.example`)
- How to set `API_KEY` as an HF Spaces secret

Update `CLAUDE.md` with the same setup instructions.

**Acceptance criteria:**
- A developer can clone the repo and follow the README to run the service locally without prior knowledge of the project
- The HF Space deploys successfully when the Docker image builds

**Dependencies:** T-05, T-19

---

## Summary

| Phase | Tasks | Key output |
|---|---|---|
| 0 — Setup | T-01 to T-05 | Runnable skeleton, Docker, CI-ready config |
| 1 — PDF Extraction | T-06 to T-08 | Text + OCR extraction with validation |
| 2 — LLM Extraction | T-09 to T-10 | Model loading + field extraction |
| 3 — Validation | T-11 to T-12 | Pydantic schema + business rule checks |
| 4 — API Layer | T-13 to T-16 | Auth, endpoint, logging, error handling |
| 5 — Testing | T-17 to T-19 | Fixtures, unit tests, integration tests |
| 6 — Deployment | T-20 | HF Spaces deployment + documentation |
