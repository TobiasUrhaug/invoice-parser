import logging
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from tests.utils import make_pdf_bytes

_FIVE_KEYS = (
    "invoiceDate",
    "invoiceReference",
    "netAmount",
    "vatAmount",
    "totalAmount",
)


def _mock_pipeline_result() -> MagicMock:
    from app.api.v1.schemas import InvoiceResult, MonetaryAmount

    result = InvoiceResult(
        invoiceDate=None,
        invoiceReference="INV-001",
        netAmount=MonetaryAmount(amount=Decimal("100.00"), currency="NOK"),
        vatAmount=MonetaryAmount(amount=Decimal("25.00"), currency="NOK"),
        totalAmount=MonetaryAmount(amount=Decimal("125.00"), currency="NOK"),
    )
    mock = MagicMock()
    mock.run.return_value = (result, "text")
    return mock


async def test_extract_returns_request_id_header(client: AsyncClient) -> None:
    """Successful extract response includes X-Request-Id header."""
    mock_pipeline = _mock_pipeline_result()
    with patch("app.api.v1.router.Pipeline", return_value=mock_pipeline):
        response = await client.post(
            "/api/v1/extract",
            headers={"X-API-Key": "test-api-key"},
            files={"file": ("invoice.pdf", make_pdf_bytes(), "application/pdf")},
        )
    assert response.status_code == 200
    assert "x-request-id" in response.headers


async def test_extract_returns_200_with_invoice_result(client: AsyncClient) -> None:
    """Valid PDF returns 200 with all five invoice fields present."""
    mock_pipeline = _mock_pipeline_result()
    with patch("app.api.v1.router.Pipeline", return_value=mock_pipeline):
        response = await client.post(
            "/api/v1/extract",
            headers={"X-API-Key": "test-api-key"},
            files={"file": ("invoice.pdf", make_pdf_bytes(), "application/pdf")},
        )
    assert response.status_code == 200
    body = response.json()
    for key in _FIVE_KEYS:
        assert key in body


async def test_extract_all_five_keys_always_present(client: AsyncClient) -> None:
    """Response always contains all five keys even when values are null."""
    from app.api.v1.schemas import InvoiceResult

    null_result = InvoiceResult(
        invoiceDate=None,
        invoiceReference=None,
        netAmount=None,
        vatAmount=None,
        totalAmount=None,
    )
    mock_pipeline = MagicMock()
    mock_pipeline.run.return_value = (null_result, "text")
    with patch("app.api.v1.router.Pipeline", return_value=mock_pipeline):
        response = await client.post(
            "/api/v1/extract",
            headers={"X-API-Key": "test-api-key"},
            files={"file": ("invoice.pdf", make_pdf_bytes(), "application/pdf")},
        )
    assert response.status_code == 200
    body = response.json()
    for key in _FIVE_KEYS:
        assert key in body
        assert body[key] is None


async def test_error_path_emits_structured_log(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Rejected requests emit a structured log with request_id and status_code."""
    with caplog.at_level(logging.INFO, logger="app.api.v1.router"):
        await client.post(
            "/api/v1/extract",
            headers={"X-API-Key": "test-api-key"},
            files={"file": ("invoice.txt", b"not a pdf", "text/plain")},
        )

    assert len(caplog.records) >= 1
    record = caplog.records[-1]
    assert hasattr(record, "request_id")
    assert hasattr(record, "status_code")
    assert hasattr(record, "duration_ms")


async def test_extract_emits_structured_log(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Each request emits a structured log with required fields."""
    mock_pipeline = _mock_pipeline_result()
    with (
        patch("app.api.v1.router.Pipeline", return_value=mock_pipeline),
        caplog.at_level(logging.INFO, logger="app.api.v1.router"),
    ):
        await client.post(
            "/api/v1/extract",
            headers={"X-API-Key": "test-api-key"},
            files={"file": ("invoice.pdf", make_pdf_bytes(), "application/pdf")},
        )

    assert len(caplog.records) >= 1
    record = caplog.records[-1]
    assert hasattr(record, "request_id")
    assert hasattr(record, "status_code")
    assert hasattr(record, "extraction_path")
    assert hasattr(record, "duration_ms")
