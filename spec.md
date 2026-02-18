# Invoice Parsing Service — Technical Specification

**Version:** 1.0 (MVP)
**Status:** Draft
**Based on:** requirements.md

---

## 1. Overview

A stateless, self-hosted HTTP service that accepts a PDF invoice, extracts structured financial fields using a locally-running language model, and returns a normalised JSON payload. Designed for internal use at low volume (<100 invoices/day).

---

## 2. Architecture

### 2.1 Architectural Style

Stateless modular monolith. Single Python process, single deployable unit. No database, no message queue, no microservices.

Horizontal scaling is not required for MVP but is possible by running multiple replicas behind a load balancer (the stateless design permits it).

### 2.2 High-Level Request Flow

```
Client
  │
  │  POST /api/v1/extract
  │  X-API-Key: {key}
  │  Content-Type: multipart/form-data
  │  body: file={pdf}
  ▼
┌─────────────────────────────────┐
│  API Layer (FastAPI)            │
│  - Auth middleware              │
│  - Input validation             │
│  - Request/response logging     │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  Pipeline Orchestrator          │
│  Coordinates stages in order    │
└──┬──────────────────────────────┘
   │
   ├─► Stage 1: PDF Extraction
   │     - pdfplumber (text PDFs — fast path)
   │     - PaddleOCR (scanned PDFs — fallback)
   │
   ├─► Stage 2: LLM Field Extraction
   │     - Qwen2.5-1.5B-Instruct (GGUF, Q4_K_M)
   │     - via llama-cpp-python
   │     - temperature=0 (deterministic)
   │     - structured JSON prompt
   │
   └─► Stage 3: Validation
         - Pydantic schema enforcement
         - Business rule checks (numeric consistency)
         - Date normalisation
         │
         ▼
       JSON response to client
```

### 2.3 Design Principles

- **Deterministic:** LLM runs at temperature=0. Same input produces the same output.
- **Stateless:** No files or results are persisted at any point (NF-04).
- **Swappable components:** Each stage (PDF extraction, LLM, validation) is accessed through an abstract interface so it can be replaced without modifying the rest of the pipeline.
- **Fail-fast validation:** File format and size are checked before any expensive processing begins.

---

## 3. Technology Stack

| Concern | Choice | Rationale |
|---|---|---|
| Language | Python 3.12 | Required |
| Web framework | FastAPI + Uvicorn | Required |
| Package manager | uv | Fast, modern, lock-file based |
| Text PDF extraction | pdfplumber | Reliable text extraction from digital PDFs; no OCR overhead |
| Scanned PDF detection | pdfplumber (text density heuristic) | Determines which path to take |
| OCR | PaddleOCR | Layout-aware, better multi-language accuracy than Tesseract, preserves bounding boxes for future use |
| PDF-to-image | pdf2image (poppler) | Required for PaddleOCR input |
| LLM inference | llama-cpp-python | Efficient CPU inference with GGUF quantised models |
| LLM model | Qwen2.5-1.5B-Instruct (Q4_K_M GGUF) | ~1GB RAM, strong multilingual capability, runs on CPU within 30s budget |
| Schema validation | Pydantic v2 | FastAPI native, strict mode |
| Testing | pytest + httpx | Standard Python testing |
| Linting | Ruff | Fast, opinionated |
| Type checking | mypy | Static analysis |
| Containerisation | Docker | Deployment target |
| Hosting | Hugging Face Spaces (Docker SDK) | Free tier: 16GB RAM, 2 vCPUs |

---

## 4. API Specification

### 4.1 Authentication

All requests must include an `X-API-Key` header. The service compares the value against the `API_KEY` environment variable using a constant-time comparison. Requests without a valid key receive `401 Unauthorized`.

### 4.2 Endpoints

#### `POST /api/v1/extract`

Submit a PDF invoice for field extraction.

**Request:**

| Parameter | Location | Type | Required | Description |
|---|---|---|---|---|
| `X-API-Key` | Header | string | Yes | API key for authentication |
| `file` | Form field | PDF file | Yes | The invoice file (multipart/form-data) |

**Constraints:**
- Accepted MIME type: `application/pdf`
- Maximum file size: 10 MB

**Response — 200 OK:**

```json
{
  "invoiceDate": "2024-01-15",
  "invoiceReference": "INV-2024-001",
  "netAmount": {
    "amount": 10000.00,
    "currency": "NOK"
  },
  "vatAmount": {
    "amount": 2500.00,
    "currency": "NOK"
  },
  "totalAmount": {
    "amount": 12500.00,
    "currency": "NOK"
  }
}
```

Fields that cannot be extracted are present with a value of `null`, not omitted:

```json
{
  "invoiceDate": "2024-01-15",
  "invoiceReference": null,
  "netAmount": null,
  "vatAmount": null,
  "totalAmount": {
    "amount": 12500.00,
    "currency": "NOK"
  }
}
```

**Monetary field schema:**

Each monetary field, when not null, is an object:

```json
{
  "amount": 12500.00,
  "currency": "NOK"
}
```

`amount` is a number (decimal). `currency` is an ISO 4217 currency code string, or `null` if not detectable.

**`invoiceDate` format:** ISO 8601 date string (`YYYY-MM-DD`). The LLM is instructed to normalise dates from any format or language into this form.

#### `GET /health`

Liveness check. Returns service status and whether the model is loaded.

**Response — 200 OK:**

```json
{
  "status": "ok",
  "model_loaded": true
}
```

### 4.3 Error Responses

All error responses use this envelope:

```json
{
  "error": "Human-readable description of the problem"
}
```

| HTTP Status | Condition |
|---|---|
| `400 Bad Request` | File is not a PDF, or file is corrupt / unreadable |
| `401 Unauthorized` | Missing or invalid API key |
| `413 Content Too Large` | File exceeds 10 MB |
| `500 Internal Server Error` | Unhandled processing failure |
| `503 Service Unavailable` | LLM model not yet loaded (cold start) |

---

## 5. Component Design

### 5.1 PDF Extraction Layer

**Interface:** `PDFExtractor` — single method `extract_text(file_bytes: bytes) -> str`

**Behaviour:**

1. Attempt text extraction using pdfplumber.
2. Compute text density (characters extracted / number of pages).
3. If text density exceeds a configurable threshold (`MIN_TEXT_CHARS_PER_PAGE`, default: 50), return the extracted text directly.
4. Otherwise, treat the document as scanned: convert pages to images using pdf2image, run PaddleOCR, and return the combined OCR text.

**Rationale:** Text-based PDFs are the common case for machine-generated invoices. Skipping OCR for these keeps latency under 1 second for the extraction step.

### 5.2 LLM Extraction Layer

**Interface:** `FieldExtractor` — single method `extract_fields(text: str) -> dict`

**Model:** `Qwen2.5-1.5B-Instruct` in GGUF format (Q4_K_M quantisation). Downloaded from Hugging Face Hub on first startup and cached at `MODEL_DIR` (environment variable, default: `/app/models`).

**Inference:** `llama-cpp-python` with `n_gpu_layers=0` (CPU only for MVP). `temperature=0`, `max_tokens=512`.

**Prompt structure:**

The system prompt instructs the model to:
- Act as an invoice data extraction assistant
- Return only a valid JSON object with exactly the five target keys
- Normalise dates to ISO 8601 (`YYYY-MM-DD`)
- Express monetary values as `{"amount": <number>, "currency": "<ISO 4217>"}` or `null`
- Set any field it cannot confidently determine to `null`
- Handle any European language without being told the language in advance

The user prompt is the raw extracted text from Stage 1, prefixed with a brief instruction.

**Output parsing:**

The raw LLM output is parsed with `json.loads`. If parsing fails (e.g. the model produces surrounding prose), a regex extracts the first JSON object from the response. If extraction still fails, all fields are returned as `null`.

### 5.3 Validation Layer

**Interface:** `InvoiceValidator` — single method `validate(raw: dict) -> InvoiceResult`

**Responsibilities:**

1. **Pydantic schema enforcement:** Cast raw extracted values to the `InvoiceResult` schema. Type coercion errors set the affected field to `null`.
2. **Date normalisation:** If `invoiceDate` is present but not already ISO 8601, attempt to parse and reformat it.
3. **Numeric consistency check:** If all three of `netAmount`, `vatAmount`, and `totalAmount` are non-null, verify that `net + vat ≈ total` within a 1% tolerance. If the check fails, log a warning but do not modify or nullify the values — return them as-is and let the caller decide.
4. **Amount sign check:** Warn if any monetary amount is negative (could be a credit note; not rejected, only logged).

### 5.4 Pipeline Orchestrator

**Module:** `services/pipeline.py`

Instantiates and calls the three stages in sequence. Handles exceptions from each stage:
- Exceptions from the PDF extraction stage propagate as `400` errors (bad input).
- Exceptions from the LLM or validation stage propagate as `500` errors (internal failure).

---

## 6. Non-Functional Requirements

| ID | Category | Specification |
|---|---|---|
| NF-01 | Performance | p95 response time < 30 seconds under normal load |
| NF-02 | Scalability | Handles < 100 invoices/day on a single instance. No horizontal scaling required for MVP. |
| NF-03 | Security | `X-API-Key` header required on all requests. Constant-time comparison to prevent timing attacks. |
| NF-04 | Statelessness | No files, OCR output, or extracted data are written to disk or any external store at any point. |
| NF-05 | Availability | Best-effort. HF Spaces free tier may have cold-start delays (~30s on first request after idle). Acceptable for MVP. |
| NF-06 | Observability | Every request is logged as a structured JSON line to stdout. |

---

## 7. Observability

Each request produces a single structured log entry on completion (or on error). No files are stored.

**Log fields:**

```json
{
  "timestamp": "2024-01-15T10:23:01.123Z",
  "request_id": "a1b2c3d4",
  "method": "POST",
  "path": "/api/v1/extract",
  "status_code": 200,
  "file_size_bytes": 204800,
  "outcome": "success",
  "extraction_path": "text",
  "null_fields": [],
  "duration_ms": 8423
}
```

`outcome` is one of: `success` (all fields extracted), `partial` (one or more fields null), `error`.
`extraction_path` is one of: `text` (pdfplumber fast path), `ocr` (PaddleOCR fallback).

---

## 8. Project Structure

```
invoice-parser/
├── app/
│   ├── main.py                  # FastAPI app instantiation, lifespan handler
│   ├── api/
│   │   └── v1/
│   │       ├── router.py        # Route definitions
│   │       └── schemas.py       # Pydantic request/response models
│   ├── services/
│   │   ├── pipeline.py          # Orchestrates the three stages
│   │   ├── pdf_extractor.py     # Stage 1: text extraction + OCR fallback
│   │   ├── llm_extractor.py     # Stage 2: LLM inference + output parsing
│   │   └── validator.py         # Stage 3: schema + business rule validation
│   └── core/
│       ├── config.py            # Settings via pydantic-settings (env vars)
│       ├── security.py          # API key dependency
│       └── logging.py           # Structured JSON log formatter
├── tests/
│   ├── test_pdf_extractor.py
│   ├── test_llm_extractor.py
│   ├── test_validator.py
│   ├── test_api.py
│   └── fixtures/                # Sample PDF invoices for testing
├── Dockerfile
├── pyproject.toml
├── .env.example
└── README.md
```

---

## 9. Deployment

### Hosting

Hugging Face Spaces (Docker SDK). The space is configured with a persistent `/data` volume only for model file caching (not for invoice data — model files are large and should survive restarts without re-downloading).

### Model Initialisation

The LLM model is downloaded from Hugging Face Hub at application startup if not already present in `MODEL_DIR`. The FastAPI lifespan handler manages this. During model loading, the `/health` endpoint returns `"model_loaded": false` and extraction requests return `503`.

### Dockerfile (outline)

```
Base image: python:3.12-slim
System deps: poppler-utils (for pdf2image), libgomp1 (for PaddleOCR)
uv install: production dependencies only
COPY app source
EXPOSE 7860
CMD: uvicorn app.main:app --host 0.0.0.0 --port 7860
```

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `API_KEY` | Yes | — | Secret key for `X-API-Key` authentication |
| `MODEL_DIR` | No | `/app/models` | Path for model file storage/cache |
| `MODEL_REPO_ID` | No | `Qwen/Qwen2.5-1.5B-Instruct-GGUF` | Hugging Face model repository |
| `MODEL_FILENAME` | No | `qwen2.5-1.5b-instruct-q4_k_m.gguf` | GGUF file to download |
| `MIN_TEXT_CHARS_PER_PAGE` | No | `50` | Threshold for text vs. scanned PDF detection |
| `MAX_FILE_SIZE_MB` | No | `10` | Maximum accepted file size |

---

## 10. Future Considerations

The following extensions are explicitly out of scope for MVP but the architecture is designed to accommodate them without rewrites:

| Extension | How the architecture supports it |
|---|---|
| Fine-tuned extraction model | Replace `LLMExtractor` implementation; interface is unchanged |
| Image format input (JPEG, PNG) | Add an image-to-text pre-processor before Stage 1; pipeline is unchanged |
| Async processing / webhooks | Wrap the pipeline in a task queue worker; the pipeline itself is already a pure function |
| Persistence / audit trail | Add a storage adapter called after Stage 3; requires conscious privacy and data handling decisions |
| Larger model (7–8B) on GPU | Change `n_gpu_layers` and deploy to a GPU-enabled host; no code changes to the pipeline |
| Batch processing | Add a batch endpoint that calls the pipeline once per file |
