"""Integration tests for the invoice parser API.

These tests exercise the full HTTP stack: authentication, input validation,
PDF extraction, and response schema. The LLM is mocked (via the shared
``client`` fixture) so no model download is required.

Run only unit tests:
    uv run pytest -m "not integration"

Run only integration tests:
    uv run pytest -m integration
"""

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.main import app
from tests.utils import make_pdf_bytes

_FIVE_KEYS = (
    "invoiceDate",
    "invoiceReference",
    "netAmount",
    "vatAmount",
    "totalAmount",
)
_FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.integration
async def test_get_health_returns_200(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True


@pytest.mark.integration
async def test_post_extract_no_api_key_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/extract",
        files={"file": ("invoice.pdf", make_pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 401


@pytest.mark.integration
async def test_post_extract_non_pdf_returns_400(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/extract",
        headers={"X-API-Key": "test-api-key"},
        files={"file": ("invoice.txt", b"not a pdf", "text/plain")},
    )

    assert response.status_code == 400
    assert "error" in response.json()


@pytest.mark.integration
async def test_post_extract_pdf_with_invalid_magic_bytes_returns_400(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/extract",
        headers={"X-API-Key": "test-api-key"},
        files={"file": ("invoice.pdf", b"not a real pdf", "application/pdf")},
    )

    assert response.status_code == 400
    assert "error" in response.json()


@pytest.mark.integration
async def test_post_extract_oversized_file_returns_413(client: AsyncClient) -> None:
    oversized = b"x" * (11 * 1024 * 1024)
    response = await client.post(
        "/api/v1/extract",
        headers={"X-API-Key": "test-api-key"},
        files={"file": ("invoice.pdf", oversized, "application/pdf")},
    )

    assert response.status_code == 413
    assert "error" in response.json()


@pytest.mark.integration
async def test_post_extract_valid_pdf_returns_200_with_schema(
    client: AsyncClient,
) -> None:
    """Valid PDF returns 200 with all five invoice fields present and non-null."""
    app.state.llm.extract_fields.return_value = {
        "invoiceDate": "2024-01-15",
        "invoiceReference": "INV-2024-001",
        "netAmount": {"amount": 1000.0, "currency": "USD"},
        "vatAmount": {"amount": 250.0, "currency": "USD"},
        "totalAmount": {"amount": 1250.0, "currency": "USD"},
    }
    pdf_bytes = (_FIXTURES_DIR / "invoice_english.pdf").read_bytes()

    response = await client.post(
        "/api/v1/extract",
        headers={"X-API-Key": "test-api-key"},
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    for key in _FIVE_KEYS:
        assert key in body
        assert body[key] is not None
