from unittest.mock import MagicMock, patch

import pytest

from app.api.v1.schemas import InvoiceResult
from app.services.pdf_extractor import ExtractionResult


def _mock_llm() -> MagicMock:
    llm = MagicMock()
    llm.extract_fields.return_value = {
        "invoiceDate": "2024-01-15",
        "invoiceReference": "INV-001",
        "netAmount": {"amount": 100.0, "currency": "NOK"},
        "vatAmount": {"amount": 25.0, "currency": "NOK"},
        "totalAmount": {"amount": 125.0, "currency": "NOK"},
    }
    return llm


def test_pipeline_run_returns_invoice_result_for_text_pdf() -> None:
    from app.services.pipeline import Pipeline

    pdf_bytes = b"%PDF-1.4 fake"
    extraction = ExtractionResult(text="Invoice text", path="text")
    llm = _mock_llm()

    with patch(
        "app.services.pipeline.SmartPDFExtractor.extract",
        return_value=extraction,
    ):
        pipeline = Pipeline(llm=llm)
        result, path = pipeline.run(pdf_bytes)

    assert isinstance(result, InvoiceResult)
    assert path == "text"
    assert result.invoiceReference == "INV-001"


def test_pipeline_run_returns_ocr_path_when_ocr_used() -> None:
    from app.services.pipeline import Pipeline

    pdf_bytes = b"%PDF-1.4 fake"
    extraction = ExtractionResult(text="Scanned text", path="ocr")
    llm = _mock_llm()

    with patch(
        "app.services.pipeline.SmartPDFExtractor.extract",
        return_value=extraction,
    ):
        pipeline = Pipeline(llm=llm)
        result, path = pipeline.run(pdf_bytes)

    assert path == "ocr"


def test_pipeline_pdf_extraction_error_propagates() -> None:
    from app.services.pipeline import Pipeline

    with patch(
        "app.services.pipeline.SmartPDFExtractor.extract",
        side_effect=ValueError("bad pdf"),
    ):
        pipeline = Pipeline(llm=_mock_llm())
        with pytest.raises(ValueError, match="bad pdf"):
            pipeline.run(b"%PDF")


def test_pipeline_llm_error_propagates() -> None:
    from app.services.pdf_extractor import ExtractionResult
    from app.services.pipeline import Pipeline

    extraction = ExtractionResult(text="some text", path="text")
    llm = MagicMock()
    llm.extract_fields.side_effect = RuntimeError("model timeout")

    with patch(
        "app.services.pipeline.SmartPDFExtractor.extract",
        return_value=extraction,
    ):
        pipeline = Pipeline(llm=llm)
        with pytest.raises(RuntimeError, match="model timeout"):
            pipeline.run(b"%PDF")


def test_pipeline_validator_error_propagates() -> None:
    from app.services.pdf_extractor import ExtractionResult
    from app.services.pipeline import Pipeline

    extraction = ExtractionResult(text="some text", path="text")
    llm = _mock_llm()

    with (
        patch(
            "app.services.pipeline.SmartPDFExtractor.extract",
            return_value=extraction,
        ),
        patch(
            "app.services.pipeline.InvoiceValidator.validate",
            side_effect=RuntimeError("validator crash"),
        ),
    ):
        pipeline = Pipeline(llm=llm)
        with pytest.raises(RuntimeError, match="validator crash"):
            pipeline.run(b"%PDF")
