---
title: Invoice Parser
emoji: 📄
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# Invoice Parser

Stateless HTTP service that extracts structured fields from PDF invoices using a local LLM. Supports both digital (text-based) and scanned (OCR) PDFs in any European language.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- `llama-cpp-python` requires a C++ compiler and cmake. For CPU-only builds, set `CMAKE_ARGS="-DGGML_BLAS=OFF"` before installing:
  ```bash
  CMAKE_ARGS="-DGGML_BLAS=OFF" uv sync
  ```

## Installation

```bash
uv sync
```

## Environment Variables

Copy `.env.example` and fill in the required values:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `API_KEY` | Yes | — | Secret key for `X-API-Key` authentication |
| `MODEL_DIR` | No | `/app/models` | Path where the GGUF model file is stored/cached |
| `MODEL_REPO_ID` | No | `Qwen/Qwen2.5-1.5B-Instruct-GGUF` | Hugging Face model repository |
| `MODEL_FILENAME` | No | `qwen2.5-1.5b-instruct-q4_k_m.gguf` | GGUF filename to download |
| `MIN_TEXT_CHARS_PER_PAGE` | No | `50` | Minimum characters per page to consider a PDF text-based |
| `MAX_FILE_SIZE_MB` | No | `10` | Maximum accepted PDF file size in megabytes |
| `LOG_LEVEL` | No | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |

## Running Locally

```bash
uv run uvicorn app.main:app --reload
```

The service starts on `http://localhost:8000`. On startup, the LLM model will be downloaded automatically if not already cached.

## Running Tests

Run all tests (including integration tests that load the real model):

```bash
uv run pytest
```

Run fast tests only (skips integration tests):

```bash
uv run pytest -m "not integration"
```

Run a single test:

```bash
uv run pytest tests/test_validator.py::test_valid_dict_produces_correct_invoice_result
```

## Linting and Type Checking

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app/
```

## Docker

```bash
docker build -t invoice-parser .
docker run -e API_KEY=your-secret-key -p 7860:7860 invoice-parser
```

## Deploying to Hugging Face Spaces

This repository is configured for deployment as a Docker-based Hugging Face Space.

1. Create a new Space on [Hugging Face](https://huggingface.co/new-space) and select **Docker** as the SDK.
2. Push this repository to the Space.
3. Set `API_KEY` as a **Secret** in the Space settings (Settings → Repository secrets).

The Space will build the Docker image and start the service on port 7860 automatically.
