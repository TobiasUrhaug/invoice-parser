## JsonFormatter silently drops exception tracebacks

**File:** `app/core/logging.py`, line 35–46
**Severity:** major

`JsonFormatter.format()` never renders `exc_info` into the JSON output. The `exc_info` key is in `_EXTRA_SKIP`, so it is filtered out of the `__dict__` loop, and the formatter never calls `self.formatException(record.exc_info)` to convert the traceback to a string.

The direct consequence is in `app/main.py`: `unhandled_exception_handler` uses `logger.exception(...)`, which sets `exc_info` on the log record precisely to capture the full traceback. With the current formatter that traceback is silently swallowed. An operator debugging a production 500 will see only the message `"Unhandled exception on POST /..."` with no stack trace.

Fix by checking `record.exc_info` after building the base payload and, if present, appending a rendered traceback string (e.g. via `self.formatException(record.exc_info)`) under a key such as `"exception"`.

**Addressed:** Added `if record.exc_info: payload["exception"] = self.formatException(record.exc_info)` to `JsonFormatter.format()`. Added `test_json_formatter_renders_exception_info` in `test_logging.py` to verify the traceback is rendered under the `"exception"` key.

---

## Error paths emit no structured log

**File:** `app/api/v1/router.py`, line 48–54
**Severity:** major

The `logger.info(...)` call only executes on the happy path, after a successful pipeline run. If `FileTooLargeError` or `InvalidMagicBytesError` is raised and converted to an HTTPException, the request completes with a 400 or 413 but leaves no structured log entry — no `request_id`, no `duration_ms`, no `status_code`, nothing. A sustained wave of malformed requests would be invisible in structured logs.

Fix by moving the timing start and request-ID generation to before the validation block, and emitting a log record in all branches (or in a `finally` block) that includes the resolved status code.

**Addressed:** Restructured the `extract` endpoint to track `status_code` (defaulting to 500, set to 400/413/200 in each branch) and moved `logger.info` into a `finally` block so it always fires with the resolved `status_code`, `request_id`, and `duration_ms`. Added `test_error_path_emits_structured_log` in `test_extract_endpoint.py` to verify logs are emitted on rejected requests.

---

## LLM and validator error paths in Pipeline are untested

**File:** `tests/test_pipeline.py`
**Severity:** major

`test_pipeline.py` covers only three paths: text extraction, OCR extraction, and a `ValueError` raised by `SmartPDFExtractor`. There are no tests for:

- `llm.extract_fields()` raising an exception (e.g., a model crash or timeout). The pipeline would propagate this uncaught, giving a 500 with no domain context.
- `validator.validate()` raising an unexpected exception (unlikely with the current implementation's defensive fallbacks, but still an untested assumption).

These are real failure modes in production. Add tests that confirm the pipeline propagates (or wraps) these errors in a predictable way, consistent with how the router's exception handlers expect to handle them.

**Addressed:** Added `test_pipeline_llm_error_propagates` and `test_pipeline_validator_error_propagates` to `test_pipeline.py`. Both confirm the pipeline propagates exceptions uncaught.

---

## `request_id` is logged but never returned to the caller

**File:** `app/api/v1/router.py`, line 35
**Severity:** minor

A UUID `request_id` is generated per request and included in the structured log. Clients have no way to discover it. When a user reports a failed request, they cannot provide a `request_id` for operators to look up in the log aggregator.

Return the ID in a response header (e.g. `X-Request-Id`) so that clients can surface it in bug reports.

**Addressed:** Added `headers={"X-Request-Id": request_id}` to the success `JSONResponse`. Added `test_extract_returns_request_id_header` to `test_extract_endpoint.py` to verify the header is present.

---

## `caplog` fixture type annotation is wrong in test

**File:** `tests/test_extract_endpoint.py`, line 73
**Severity:** minor

`test_extract_emits_structured_log(client: AsyncClient, caplog: logging.LogRecord)` annotates `caplog` as `logging.LogRecord`. The pytest fixture is `pytest.LogCaptureFixture`. The wrong annotation is misleading and would be caught by mypy if tests were included in its scope.

Change the annotation to `pytest.LogCaptureFixture`.

**Addressed:** Updated the annotation on both `test_extract_emits_structured_log` and the new `test_error_path_emits_structured_log` to use `pytest.LogCaptureFixture`. Added `import pytest` at the top of `test_extract_endpoint.py`.

---

## Null field serialization not asserted — only key presence is checked

**File:** `tests/test_extract_endpoint.py`, line 48–70
**Severity:** minor

`test_extract_all_five_keys_always_present` only asserts `key in body` for a result where all five fields are `None`. It does not assert that those keys map to JSON `null` (i.e. `body[key] is None`). A response that omits the keys or maps them to empty strings or `0` would pass this test.

The contract being tested is "all five keys are always present, with `null` for missing values". Assert `body[key] is None` for each key in the null-result scenario to make the contract explicit.

**Addressed:** Added `assert body[key] is None` inside the loop in `test_extract_all_five_keys_always_present`.

---

## `configure_logging` destroys pytest's log-capture handler

**File:** `app/core/logging.py`, line 53
**Severity:** minor

`root.handlers = [handler]` replaces all existing handlers on the root logger. In tests, the `client` fixture triggers the app lifespan, which calls `configure_logging`, which removes pytest's internal `LogCaptureHandler`. Subsequent uses of `caplog` in the same test may capture nothing.

`test_extract_emits_structured_log` relies on `caplog` working correctly after the client fixture has already run the lifespan. Whether it passes in practice depends on pytest's implementation details around handler re-installation; it is fragile either way.

Fix by appending the JSON handler rather than replacing all handlers, or by using `logging.config.dictConfig` with `incremental` mode in tests.

**Addressed:** Changed `root.handlers = [handler]` to `root.addHandler(handler)` in `configure_logging`.

---

## `MagicMock` import inside fixture body

**File:** `tests/conftest.py`, line 57
**Severity:** nit

`from unittest.mock import MagicMock` is imported inside the `client` fixture function. Top-level imports are the convention in Python; lazy imports inside functions are reserved for cases where the import is conditional or circular. Move this to the top of the file alongside the other imports.

**Addressed:** Moved `from unittest.mock import MagicMock` to the top-level imports in `conftest.py` and removed the inline import from inside the `client` fixture.

---

## Two test functions spin up the same app and hit the same endpoint

**File:** `tests/test_error_handling.py`, lines 21–38
**Severity:** nit

`test_unhandled_exception_returns_500_with_error_envelope` and `test_unhandled_exception_does_not_return_fastapi_default_shape` each call `_make_app_with_error_route()`, construct a `TestClient`, and issue an identical `GET /boom` request. They differ only in their assertions. Consider merging them into a single test that asserts both the status code and the response shape, or extracting the response into a shared fixture.

**Addressed:** Merged the two tests into `test_unhandled_exception_returns_500_error_envelope` which asserts status code, presence of `"error"`, absence of `"detail"`, and absence of the internal exception message.

---

## `_INVOICE_FIELDS` in router duplicates schema field names

**File:** `app/api/v1/router.py`, lines 22–28
**Severity:** nit

The tuple `_INVOICE_FIELDS` hardcodes the same five field names that already live in `InvoiceResult`. `_FIVE_KEYS` in `llm_extractor.py` does the same. If `InvoiceResult` ever gains or loses a field, all three must be updated manually with no compile-time enforcement.

Derive the field names from the schema directly — e.g. `tuple(InvoiceResult.model_fields.keys())` — so there is a single source of truth.

**Addressed:** Replaced the hardcoded `_INVOICE_FIELDS` tuple in `router.py` with `tuple(InvoiceResult.model_fields.keys())`.

---

## `invoice_partial` expected output contradicts the invoice text

**File:** `tests/fixtures/invoice_partial.json`, `tests/fixtures/generate_fixtures.py`, line 230
**Severity:** major

The `invoice_partial` invoice contains the line `"No VAT applies. Total equals net amount."`, but the expected JSON has `totalAmount: null`. Any LLM following the system prompt — "set undetectable fields to null" — will read that sentence and correctly infer the total is EUR 300.00. It will not return null.

This creates a false regression failure: the pipeline produces a reasonable answer, but the fixture says it is wrong. Integration tests built on this fixture will fail consistently, not because of a bug but because the expected output is incorrect.

To actually test null field handling for `totalAmount`, remove any mention of a total from the invoice text. Or, if the intent is merely to test `vatAmount: null`, update the expected JSON so `totalAmount` matches what the LLM would actually return (EUR 300.00).

**Addressed:** Removed the line `"No VAT applies. Total equals net amount."` from the `invoice_partial` fixture in `generate_fixtures.py`. The invoice no longer states a total amount, making `totalAmount: null` a defensible expectation. Regenerated `invoice_partial.pdf` and `invoice_partial.json`.

---

## German fixture avoids umlauts — does not test non-ASCII handling

**File:** `tests/fixtures/generate_fixtures.py`, lines 156–178
**Severity:** minor

The German invoice uses ASCII substitutes throughout: `"Muenchen"` instead of `"München"`, `"Hauptstrasse"` instead of `"Hauptstraße"`. This is a workaround for the Helvetica Type1 font in `_make_text_pdf`, which cannot render non-ASCII characters without explicit encoding.

The rationale for a non-English fixture is to verify the pipeline handles European languages — including their special characters. A German invoice that never uses an umlaut does not exercise that risk. A real German invoice would contain ä, ö, ü, ß. If the PDF encoding pipeline cannot produce them, the fixture should at least be documented as deliberately ASCII-only, and a separate note added to T-19 to verify non-ASCII handling manually or via a separately sourced fixture.

**Addressed:** Added a `# NOTE: Deliberately ASCII-only` comment block on the `invoice_german` fixture entry in `generate_fixtures.py` explaining the font limitation. Added a "Non-ASCII handling" pre-implementation note to T-19 in `tasks.md` directing implementers to source a Unicode-capable fixture for end-to-end umlaut verification.

---

## OCR fixture expected values are unverified against actual OCR output

**File:** `tests/fixtures/invoice_scanned.json`
**Severity:** minor

The expected output in `invoice_scanned.json` assumes the OCR + LLM pipeline will return exact values (`"SCAN-001"`, `"2024-03-10"`, `"500.00"`, etc.). These values were not derived by running the pipeline against the fixture — they were defined in `generate_fixtures.py` and written directly to the JSON file.

OCR accuracy depends on font rendering, image quality, and engine version. The PIL default bitmap font at size 14 used by `_make_image_pdf` is legible to a human but may produce character-level errors in PaddleOCR. If OCR returns `"SCAN-OO1"` or `"2O24-O3-1O"` (zeros misread as O's), the integration test fails spuriously with no code bug present.

Run the actual pipeline against `invoice_scanned.pdf` and update `invoice_scanned.json` with the real output before wiring this fixture into T-19 integration tests.

**Addressed:** Added an "OCR fixture verification" pre-implementation note to T-19 in `tasks.md` requiring implementers to run the actual pipeline against `invoice_scanned.pdf` and update the expected JSON before using the fixture in integration tests.

---

## `_make_image_pdf` defines an unused font object

**File:** `tests/fixtures/generate_fixtures.py`, line 100
**Severity:** nit

`obj5` defines a Helvetica font in the image PDF, but the content stream (`q {w} 0 0 {h} 0 0 cm /Im1 Do Q`) only references the image XObject `Im1`. No text operators use `/F1`, so the font object is unreferenced dead weight in the PDF structure.

Remove `obj5` from `_make_image_pdf` and adjust the xref table from `0 7` to `0 6` accordingly.

**Addressed:** Removed the unused font `obj5` from `_make_image_pdf`. Renumbered the image XObject from `6 0 obj` to `5 0 obj`, updated the page resources reference from `6 0 R` to `5 0 R`, and changed the xref table from `0 7` to `0 6`. Regenerated `invoice_scanned.pdf`.

---

## Coverage enforcement not wired into the default test command

**File:** `pyproject.toml`, line 42–45
**Severity:** minor

T-18's acceptance criterion states that `uv run pytest tests/ -k "not integration"` should pass with `>80% coverage on service modules`. However, `[tool.pytest.ini_options]` has no `addopts` entry enabling coverage. Running the stated command produces no coverage report and therefore cannot verify the threshold automatically. A developer or CI pipeline following the acceptance criterion literally would see all tests pass but have no confirmation that coverage was measured at all.

Add `addopts = "--cov=app/services --cov-report=term-missing"` (or similar) to `[tool.pytest.ini_options]` so that coverage is measured on every test run and the threshold is always visible without requiring extra flags.

**Addressed:** Added `addopts = "--cov=app/services --cov-report=term-missing"` to `[tool.pytest.ini_options]` in `pyproject.toml`. Coverage now runs automatically and reports 100% on all service modules.

---

## Inner `except ValidationError` block in `_coerce` is unreachable and untested

**File:** `app/services/validator.py`, lines 119–127
**Severity:** minor

The inner `try/except ValidationError` block (lines 118–127 in `_coerce`) catches a second `ValidationError` raised by `InvoiceResult.model_validate(cleaned)` after the cleanup loop has already nullified every field that caused the first error. Setting a field to `None` cannot introduce a new `ValidationError` because every field in `InvoiceResult` is typed as `T | None`. The inner catch is therefore unreachable with the current schema, and lines 120–121 are the only two lines not covered in the entire service layer (visible in `--cov-report=term-missing` output: 97% on `validator.py`).

The dead code inflates complexity without adding safety. Either remove the inner `try/except` and let any unexpected second `ValidationError` propagate (making it visible instead of silent), or add a test that exercises it by injecting a schema where nullifying a field can still fail — to confirm the fallback is actually needed. Leaving unreachable code in place gives a false sense of defence.

**Addressed:** Removed the inner `try/except ValidationError` block from `_coerce`. The second `model_validate(cleaned)` call now propagates any unexpected error rather than swallowing it. Service coverage is now 100% (was 97%).

---

## Test comments couple test documentation to private implementation details

**File:** `tests/test_llm_extractor.py`, lines 157–158
**Severity:** nit

The docstring comment in `test_extract_fields_returns_all_null_when_opening_brace_is_never_closed` reads:

```
# json.loads fails; _extract_json_object finds "{" but no matching "}"
# → returns None → all fields fall back to null.
```

This names `_extract_json_object`, a private helper, and traces the internal call path rather than describing observable behaviour. If `_extract_json_object` is renamed or inlined, this comment becomes stale without any compile-time signal. The test name already captures the observable contract precisely. Remove the comment entirely, or replace it with a behavioural description that does not reference internal function names (e.g. `# LLM output has an open brace that is never closed — brace-matching falls back gracefully`).

**Addressed:** Replaced the two implementation-detail comment lines with `# LLM output has an open brace that is never closed — graceful fallback to all-null`.

---

## `app.state.llm` stores a `Llama` but `Pipeline` expects `LLMExtractor` — production crash on every extract request

**File:** `app/main.py`, line 24; `app/api/v1/router.py`, line 62; `app/services/pipeline.py`, line 10
**Severity:** critical

`main.py` stores the raw model in app state:

```python
application.state.llm = init_model(...)  # returns Llama
```

The router then passes it directly to `Pipeline`:

```python
llm = request.app.state.llm
pipeline = Pipeline(llm=llm)
```

`Pipeline.__init__` is typed `llm: LLMExtractor` and `Pipeline.run()` calls `self._llm.extract_fields(text)`. A `Llama` instance has no `extract_fields` method, so every real request to `POST /api/v1/extract` would raise `AttributeError: 'Llama' object has no attribute 'extract_fields'`.

The integration tests mask this entirely: the `client` fixture sets `app.state.llm = MagicMock()`, and `MagicMock` auto-creates any attribute without error. No test exercises the real `Llama → Pipeline` wiring.

Fix by wrapping the model at the point it is stored — either in `main.py` (`application.state.llm = LLMExtractor(init_model(...))`) or inside the router before passing to `Pipeline` — so that `Pipeline` always receives the type its signature advertises.

**Addressed:** Added `test_lifespan_stores_llm_extractor_in_app_state` to `test_model_loading.py` (red: fails because raw `Llama` is stored). Fixed `main.py` to import `LLMExtractor` and wrap: `application.state.llm = LLMExtractor(init_model(...))` (green: test passes).

---

## Mock in valid-PDF test is wired to the wrong method — test passes vacuously

**File:** `tests/test_api.py`, lines 91–93
**Severity:** major

`test_post_extract_valid_pdf_returns_200_with_schema` configures:

```python
app.state.llm.create_chat_completion.return_value = {
    "choices": [{"message": {"content": llm_content}}]
}
```

`app.state.llm` is a `MagicMock`. The production path the router exercises is `Pipeline(llm=app.state.llm)` → `pipeline._llm.extract_fields(text)`. The configured `create_chat_completion` return value is never reached by any code in this call chain.

The test passes only because `MagicMock().extract_fields()` auto-returns a MagicMock, `dict(MagicMock())` resolves to `{}`, and the validator returns an all-null `InvoiceResult`. The five keys are present (all `null`) and the assertion `assert key in body` succeeds — but it would succeed even if extraction were completely broken.

The test should either mock `app.state.llm.extract_fields.return_value` with a valid `InvoiceFields` dict and assert non-null values in the response, or it should construct `app.state.llm` as an `LLMExtractor` wrapping a mock `Llama` with `create_chat_completion` configured.

**Addressed:** Changed mock to `app.state.llm.extract_fields.return_value = {valid InvoiceFields dict}` and added `assert body[key] is not None` inside the loop. Removed the unused `import json`. The test now verifies the full extraction pipeline returns populated values.

---

## `InvalidMagicBytesError` path is untested

**File:** `tests/test_api.py`
**Severity:** minor

`test_post_extract_non_pdf_returns_400` exercises only the `InvalidContentTypeError` path (MIME type `text/plain`). There is no test for a file declared as `application/pdf` but missing the `%PDF` magic bytes — the `InvalidMagicBytesError` branch in `validate_pdf` is left untested.

The magic bytes check is the defence against misnamed files (e.g. a JPEG renamed to `.pdf`). Add a test that sends `content_type="application/pdf"` with bytes that do not start with `%PDF` and asserts a 400 response with an `"error"` key.

**Addressed:** Added `test_post_extract_pdf_with_invalid_magic_bytes_returns_400` to `test_api.py`: sends `content_type="application/pdf"` with non-`%PDF` bytes and asserts status 400 with an `"error"` key.

---

## Health test does not assert `model_loaded`

**File:** `tests/test_api.py`, lines 34–39
**Severity:** minor

`test_get_health_returns_200` asserts `body["status"] == "ok"` but ignores `body["model_loaded"]`. The health endpoint's `model_loaded` field is the primary signal clients use to determine whether the service is ready to accept extraction requests. The `client` fixture explicitly sets `app.state.model_loaded = True`, making the value predictable. Add `assert body["model_loaded"] is True` to verify the field is present and correct.

**Addressed:** Added `assert body["model_loaded"] is True` to `test_get_health_returns_200`.

---

## Direct import from `conftest.py` is unconventional and fragile

**File:** `tests/test_api.py`, line 21
**Severity:** nit

`from tests.conftest import make_pdf_bytes` imports a utility function directly from `conftest.py` by module path. `conftest.py` is a pytest-specific file intended for fixtures and hooks, not general utility functions. Direct imports from it are unconventional: if `make_pdf_bytes` is ever extracted to a proper utilities module, any import that references `tests.conftest` breaks without a compile-time signal.

Move `make_pdf_bytes` to a `tests/utils.py` (or `tests/helpers.py`) module and import it from there in both `conftest.py` and `test_api.py`.

**Addressed:** Moved `make_pdf_bytes` to `tests/utils.py` and updated all callers (`test_api.py`, `test_extract_endpoint.py`, `test_pdf_extractor.py`, `test_pdf_validation.py`) to import from `tests.utils`. Removed the function and its re-export from `conftest.py`.
