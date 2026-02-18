# Code Review Comments

Date: 2026-02-18

## Overall

The previous reviewer comments were addressed. Two new areas of work are included in this review: PDF validation in the router (`app/api/v1/router.py`) and the PDF extraction service (`app/services/pdf_extractor.py`) with their respective tests. Linting, formatting, and type checking all pass. Tests pass. But there are real issues worth fixing before building further.

---

## Auth test assertion weakened without justification

**File:** `tests/test_auth.py`, line 26
**Severity:** major

The committed `HEAD` has `assert response.status_code == 200`. The working tree reverts this to `assert response.status_code != 401`, with a comment claiming "422 is expected because no file was uploaded."

This is the wrong fix. The auth test is not a contract about what the endpoint does after auth — it is a contract about auth itself. The correct repair is to assert the exact status code that follows successful auth. Now that the endpoint requires a file, that code is `422`. Use `assert response.status_code == 422`, or send a minimal valid file and assert `== 200`. Either is a precise assertion. `!= 401` is not — a `500` would satisfy it silently.

Reverting a strengthened assertion without a better replacement is a regression.

---

## Redundant `@pytest.mark.asyncio` decorators reintroduced

**File:** `tests/test_pdf_validation.py`, lines 35, 48, 62, 75
**Severity:** nit

`pyproject.toml` sets `asyncio_mode = "auto"`. The previous reviewer flagged exactly this problem in `test_auth.py`, and the fix commit removed those decorators. Now every test in `test_pdf_validation.py` has them again. Remove them.

---

## `client` fixture typed as `object` with inline `isinstance` assertion

**File:** `tests/test_pdf_validation.py`, lines 36–39 (and similar in each test)
**Severity:** minor

```python
async def test_upload_non_pdf_content_type_returns_400(client: object) -> None:
    from httpx import AsyncClient
    assert isinstance(client, AsyncClient)
```

The `client` fixture is declared as `AsyncGenerator[AsyncClient, None]` in `conftest.py`. Type it correctly — `client: AsyncClient`. The `isinstance` assertion is a type narrowing hack that adds noise without testing anything meaningful. The module-level import should also move to the top of the file.

---

## PDF builder helper is duplicated across two test files

**File:** `tests/test_pdf_extractor.py`, line 12; `tests/test_pdf_validation.py`, line 6
**Severity:** minor

`_make_text_pdf` in `test_pdf_extractor.py` and `_make_minimal_pdf` in `test_pdf_validation.py` are essentially the same function — both construct a minimal valid PDF from scratch. Duplicated test helpers drift apart silently and make the test suite harder to maintain.

Extract a single `make_pdf_bytes(text: str = "test") -> bytes` helper into `tests/conftest.py` (or a dedicated `tests/fixtures.py`) and use it from both test files.

---

## Settings manipulation duplicated manually in extractor tests

**File:** `tests/test_pdf_extractor.py`, lines 83–84, 92, 101–102, 119
**Severity:** minor

```python
monkeypatch.setenv("API_KEY", "test-key")
get_settings.cache_clear()
# ...
get_settings.cache_clear()
```

The `conftest.py` fixture already handles this correctly — it patches the env, clears the cache before yielding, and clears it again on teardown. These tests repeat that logic by hand. If the teardown `cache_clear()` is skipped because of a mid-test failure, the cached settings leak into subsequent tests.

Import `get_settings.cache_clear` cleanup should be in a fixture, not inline. Either use an autouse fixture or extend the existing `client` fixture pattern for tests that need settings but not an HTTP client.

---

## `SmartPDFExtractor.extract()` opens the PDF twice

**File:** `app/services/pdf_extractor.py`, lines 62–64
**Severity:** minor

```python
text = self._plumber.extract_text(file_bytes)   # opens PDF
with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:  # opens it again
    page_count = len(pdf.pages)
```

`PlumberExtractor.extract_text()` already opens the PDF but discards the page count. `SmartPDFExtractor` opens it a second time just to retrieve that value. The natural fix is to return `(text, page_count)` from `extract_text`, or to extract the page-count retrieval into a separate method on `PlumberExtractor`. Opening and parsing the same PDF bytes twice is wasteful and the duplication will matter more as files get larger.

---

## PDF validation logic belongs in the service layer, not the router

**File:** `app/api/v1/router.py`, lines 15–28
**Severity:** minor

The router now validates content type, file size, and magic bytes directly in the endpoint function. This is business logic, not HTTP routing. The `pdf_extractor.py` service layer exists precisely to own PDF-related concerns. Validation should live there — or in a dedicated validator — so it can be tested independently of HTTP, reused, and kept out of the routing layer.

---

## `not file_bytes[:4] == _PDF_MAGIC` — use `!=`

**File:** `app/api/v1/router.py`, line 27
**Severity:** nit

```python
if not file_bytes[:4] == _PDF_MAGIC:
```

This is equivalent to `!=` but reads as if `not` applies to the whole condition after parsing. Write `if file_bytes[:4] != _PDF_MAGIC:` for clarity.

---

## Weak assertion in happy-path validation test

**File:** `tests/test_pdf_validation.py`, lines 85–87
**Severity:** major

```python
# The extract endpoint is a stub returning None right now, so 422 is fine;
# we just confirm it is NOT 400 or 413.
assert response.status_code not in (400, 413)
```

Two problems:

1. The comment is wrong. The endpoint is not a stub — it has real validation and returns `200` for a valid PDF (since `extract()` returns `None`, FastAPI responds with `200 null`). `422` is not "fine" here; a `422` would mean the test is broken.

2. `not in (400, 413)` accepts any other code including `500`, `503`, `401`, or `404`. A real regression would pass this test silently. Assert `== 200` if that is the current contract, or assert the exact code you expect when the extraction stub is replaced.

---

## `python-multipart` dependency not committed

**File:** `pyproject.toml`, line 18
**Severity:** major

`python-multipart` was added to `pyproject.toml` but is not staged or committed. Without it, `UploadFile` support is unavailable and every file upload request fails. Anyone checking out from `HEAD` cannot run the new validation tests. Commit this change with the rest of the work.

---

## Missing test coverage

| Scenario | Covered? |
|---|---|
| Non-PDF content type → 400 | Yes |
| Oversized file → 413 | Yes |
| Wrong magic bytes → 400 | Yes |
| Valid PDF passes validation | Yes (but assertion is too weak — see above) |
| File with correct content type and magic bytes but corrupted PDF structure | No |
| `PlumberExtractor` gracefully handles a PDF with zero pages | No |
| `_is_text_based` when `page_count = 0` | No (function returns `False` but no test verifies it) |
| `SmartPDFExtractor` when `PlumberExtractor` raises | No |
| `PaddleOCRExtractor` — no tests at all | No (OCR path is tested only through the mock) |
