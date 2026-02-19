import io
from dataclasses import dataclass
from typing import Literal

import pdfplumber

_PDF_MAGIC = b"%PDF"
_MIN_TEXT_CHARS_PER_PAGE = 50


class PDFValidationError(Exception):
    pass


class InvalidContentTypeError(PDFValidationError):
    pass


class FileTooLargeError(PDFValidationError):
    pass


class InvalidMagicBytesError(PDFValidationError):
    pass


def validate_pdf(
    content_type: str | None,
    file_bytes: bytes,
    max_size_mb: int,
) -> None:
    if content_type != "application/pdf":
        raise InvalidContentTypeError("File must be a PDF")
    if len(file_bytes) > max_size_mb * 1024 * 1024:
        raise FileTooLargeError(f"File exceeds maximum size of {max_size_mb} MB")
    if file_bytes[:4] != _PDF_MAGIC:
        raise InvalidMagicBytesError("File does not appear to be a PDF")


def _is_text_based(
    text: str,
    page_count: int,
    min_chars_per_page: int = _MIN_TEXT_CHARS_PER_PAGE,
) -> bool:
    return (len(text) / page_count) >= min_chars_per_page if page_count > 0 else False


class PlumberExtractor:
    def extract_text_and_page_count(self, file_bytes: bytes) -> tuple[str, int]:
        if not file_bytes:
            raise ValueError("file_bytes must not be empty")
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text = "\n\n".join(page.extract_text() or "" for page in pdf.pages)
            page_count = len(pdf.pages)
        return text, page_count

    def extract_text(self, file_bytes: bytes) -> str:
        return self.extract_text_and_page_count(file_bytes)[0]


class PaddleOCRExtractor:
    def extract_text(self, file_bytes: bytes) -> str:
        from paddleocr import PaddleOCR  # type: ignore[import-untyped]
        from pdf2image import convert_from_bytes

        ocr = PaddleOCR(use_textline_orientation=True, lang="en")
        images = convert_from_bytes(file_bytes)
        pages: list[str] = []
        for image in images:
            result = ocr.ocr(image, cls=True)
            lines = [
                word_info[1][0] for line in (result or []) for word_info in (line or [])
            ]
            pages.append(" ".join(lines))
        return "\n\n".join(pages)


@dataclass
class ExtractionResult:
    text: str
    path: Literal["text", "ocr"]


class SmartPDFExtractor:
    def __init__(self, min_chars_per_page: int = _MIN_TEXT_CHARS_PER_PAGE) -> None:
        self._plumber = PlumberExtractor()
        self._min_chars = min_chars_per_page

    def extract(self, file_bytes: bytes) -> ExtractionResult:
        text, page_count = self._plumber.extract_text_and_page_count(file_bytes)
        if _is_text_based(text, page_count, self._min_chars):
            return ExtractionResult(text=text, path="text")

        ocr = PaddleOCRExtractor()
        return ExtractionResult(text=ocr.extract_text(file_bytes), path="ocr")
