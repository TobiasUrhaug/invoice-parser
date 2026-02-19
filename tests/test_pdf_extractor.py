import sys
from unittest.mock import MagicMock, patch

import pytest

from app.services.pdf_extractor import (
    FileTooLargeError,
    InvalidContentTypeError,
    InvalidMagicBytesError,
    PlumberExtractor,
    SmartPDFExtractor,
    _is_text_based,
    validate_pdf,
)
from tests.utils import make_pdf_bytes

# --- PlumberExtractor ---


def test_extract_text_returns_expected_content() -> None:
    pdf_bytes = make_pdf_bytes("InvoiceNumber 12345")
    extractor = PlumberExtractor()
    result = extractor.extract_text(pdf_bytes)
    assert "InvoiceNumber" in result
    assert "12345" in result


def test_extract_text_raises_on_empty_input() -> None:
    extractor = PlumberExtractor()
    with pytest.raises(ValueError):
        extractor.extract_text(b"")


def test_extract_text_raises_on_corrupted_pdf() -> None:
    corrupted = b"%PDF-1.4 this is not a real pdf"
    extractor = PlumberExtractor()
    with pytest.raises(Exception):
        extractor.extract_text(corrupted)


def test_extract_text_and_page_count_returns_both() -> None:
    pdf_bytes = make_pdf_bytes("hello")
    extractor = PlumberExtractor()
    text, page_count = extractor.extract_text_and_page_count(pdf_bytes)
    assert "hello" in text
    assert page_count == 1


def test_plumber_extractor_returns_empty_string_for_zero_page_pdf() -> None:
    extractor = PlumberExtractor()
    mock_pdf = MagicMock()
    mock_pdf.pages = []
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    with patch("app.services.pdf_extractor.pdfplumber.open", return_value=mock_pdf):
        text, page_count = extractor.extract_text_and_page_count(b"notempty")
    assert text == ""
    assert page_count == 0


# --- _is_text_based ---


def test_is_text_based_returns_true_when_chars_per_page_meets_threshold() -> None:
    assert _is_text_based("a" * 100, page_count=1) is True


def test_is_text_based_returns_false_when_chars_per_page_below_threshold() -> None:
    assert _is_text_based("a" * 10, page_count=1) is False


def test_is_text_based_returns_false_on_empty_text() -> None:
    assert _is_text_based("", page_count=1) is False


def test_is_text_based_returns_false_when_page_count_is_zero() -> None:
    assert _is_text_based("lots of text here", page_count=0) is False


# --- validate_pdf ---


def test_validate_pdf_raises_on_non_pdf_content_type() -> None:
    with pytest.raises(InvalidContentTypeError):
        validate_pdf("image/png", b"%PDF content", max_size_mb=10)


def test_validate_pdf_raises_when_content_type_is_none() -> None:
    with pytest.raises(InvalidContentTypeError):
        validate_pdf(None, b"%PDF content", max_size_mb=10)


def test_validate_pdf_raises_on_oversized_file() -> None:
    large_bytes = b"%PDF" + b"x" * (11 * 1024 * 1024)
    with pytest.raises(FileTooLargeError):
        validate_pdf("application/pdf", large_bytes, max_size_mb=10)


def test_validate_pdf_raises_on_wrong_magic_bytes() -> None:
    with pytest.raises(InvalidMagicBytesError):
        validate_pdf("application/pdf", b"NOTPDF content here", max_size_mb=10)


def test_validate_pdf_passes_for_valid_pdf_bytes() -> None:
    validate_pdf("application/pdf", b"%PDF-1.4 content", max_size_mb=10)


# --- SmartPDFExtractor ---


def test_smart_extractor_uses_text_path_for_digital_pdf() -> None:
    # Text must be >= 50 chars per page to meet the default threshold.
    rich_text = "InvoiceNumber 12345 Date 2024-01-15 Total 1000.00 EUR"
    pdf_bytes = make_pdf_bytes(rich_text)
    extractor = SmartPDFExtractor()
    result = extractor.extract(pdf_bytes)
    assert result.path == "text"
    assert "InvoiceNumber" in result.text


def test_smart_extractor_uses_ocr_path_for_scanned_pdf() -> None:
    # A PDF with no extractable text triggers the OCR path.
    scanned_pdf = make_pdf_bytes("")  # empty text → below threshold

    fake_ocr_text = "OCR extracted text"
    mock_ocr = MagicMock()
    mock_ocr.extract_text.return_value = fake_ocr_text

    with patch(
        "app.services.pdf_extractor.PaddleOCRExtractor",
        return_value=mock_ocr,
    ):
        extractor = SmartPDFExtractor()
        result = extractor.extract(scanned_pdf)

    assert result.path == "ocr"
    assert result.text == fake_ocr_text


def test_smart_extractor_propagates_plumber_error() -> None:
    extractor = SmartPDFExtractor()
    with patch.object(
        extractor._plumber,
        "extract_text_and_page_count",
        side_effect=ValueError("corrupted"),
    ):
        with pytest.raises(ValueError, match="corrupted"):
            extractor.extract(b"somebytes")


# --- PaddleOCRExtractor ---


def test_paddle_ocr_extractor_returns_concatenated_text() -> None:
    from app.services.pdf_extractor import PaddleOCRExtractor

    mock_image = MagicMock()
    mock_ocr_instance = MagicMock()
    mock_ocr_instance.ocr.return_value = [
        [("bbox", ("text1", 0.99)), ("bbox", ("text2", 0.98))]
    ]

    mock_paddleocr_mod = MagicMock()
    mock_paddleocr_mod.PaddleOCR = MagicMock(return_value=mock_ocr_instance)
    mock_pdf2image_mod = MagicMock()
    mock_pdf2image_mod.convert_from_bytes = MagicMock(return_value=[mock_image])

    with patch.dict(
        sys.modules,
        {"paddleocr": mock_paddleocr_mod, "pdf2image": mock_pdf2image_mod},
    ):
        extractor = PaddleOCRExtractor()
        result = extractor.extract_text(b"%PDF fake bytes")

    assert "text1" in result
    assert "text2" in result
