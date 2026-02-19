from unittest.mock import MagicMock

import pytest

from app.api.v1.schemas import InvoiceResult
from app.services.pdf_extractor import ExtractionResult, SmartPDFExtractor
from app.services.pipeline import Pipeline
from app.services.validator import InvoiceValidator


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


def _mock_pdf(extraction: ExtractionResult) -> MagicMock:
    pdf = MagicMock(spec=SmartPDFExtractor)
    pdf.extract.return_value = extraction
    return pdf


def _make_pipeline(
    llm: MagicMock | None = None,
    pdf: MagicMock | None = None,
    validator: InvoiceValidator | None = None,
) -> Pipeline:
    extraction = ExtractionResult(text="Invoice text", path="text")
    return Pipeline(
        pdf=pdf or _mock_pdf(extraction),
        llm=llm or _mock_llm(),
        validator=validator or InvoiceValidator(),
    )


def test_pipeline_run_returns_invoice_result_for_text_pdf() -> None:
    extraction = ExtractionResult(text="Invoice text", path="text")
    llm = _mock_llm()
    pipeline = Pipeline(
        pdf=_mock_pdf(extraction),
        llm=llm,
        validator=InvoiceValidator(),
    )
    result, path = pipeline.run(b"%PDF-1.4 fake")

    assert isinstance(result, InvoiceResult)
    assert path == "text"
    assert result.invoiceReference == "INV-001"


def test_pipeline_run_returns_ocr_path_when_ocr_used() -> None:
    extraction = ExtractionResult(text="Scanned text", path="ocr")
    llm = _mock_llm()
    pipeline = Pipeline(
        pdf=_mock_pdf(extraction),
        llm=llm,
        validator=InvoiceValidator(),
    )
    result, path = pipeline.run(b"%PDF-1.4 fake")

    assert path == "ocr"


def test_pipeline_pdf_extraction_error_propagates() -> None:
    pdf = MagicMock(spec=SmartPDFExtractor)
    pdf.extract.side_effect = ValueError("bad pdf")
    pipeline = Pipeline(
        pdf=pdf,
        llm=_mock_llm(),
        validator=InvoiceValidator(),
    )
    with pytest.raises(ValueError, match="bad pdf"):
        pipeline.run(b"%PDF")


def test_pipeline_llm_error_propagates() -> None:
    extraction = ExtractionResult(text="some text", path="text")
    llm = MagicMock()
    llm.extract_fields.side_effect = RuntimeError("model timeout")
    pipeline = Pipeline(
        pdf=_mock_pdf(extraction),
        llm=llm,
        validator=InvoiceValidator(),
    )
    with pytest.raises(RuntimeError, match="model timeout"):
        pipeline.run(b"%PDF")


def test_pipeline_validator_error_propagates() -> None:
    extraction = ExtractionResult(text="some text", path="text")
    validator = MagicMock(spec=InvoiceValidator)
    validator.validate.side_effect = RuntimeError("validator crash")
    pipeline = Pipeline(
        pdf=_mock_pdf(extraction),
        llm=_mock_llm(),
        validator=validator,
    )
    with pytest.raises(RuntimeError, match="validator crash"):
        pipeline.run(b"%PDF")
