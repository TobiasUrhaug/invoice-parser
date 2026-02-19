from typing import Literal

from app.api.v1.schemas import InvoiceResult
from app.services.llm_extractor import LLMExtractor
from app.services.pdf_extractor import SmartPDFExtractor
from app.services.validator import InvoiceValidator


class Pipeline:
    def __init__(self, llm: LLMExtractor) -> None:
        self._pdf = SmartPDFExtractor()
        self._llm = llm
        self._validator = InvoiceValidator()

    def run(self, file_bytes: bytes) -> tuple[InvoiceResult, Literal["text", "ocr"]]:
        extraction = self._pdf.extract(file_bytes)
        raw = self._llm.extract_fields(extraction.text)
        result = self._validator.validate(dict(raw))
        return result, extraction.path
