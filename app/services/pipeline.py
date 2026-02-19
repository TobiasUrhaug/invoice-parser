from typing import Literal

from app.api.v1.schemas import InvoiceResult
from app.services.llm_extractor import LLMExtractor
from app.services.pdf_extractor import SmartPDFExtractor
from app.services.validator import InvoiceValidator


class Pipeline:
    def __init__(
        self,
        pdf: SmartPDFExtractor,
        llm: LLMExtractor,
        validator: InvoiceValidator,
    ) -> None:
        self._pdf = pdf
        self._llm = llm
        self._validator = validator

    def run(self, file_bytes: bytes) -> tuple[InvoiceResult, Literal["text", "ocr"]]:
        extraction = self._pdf.extract(file_bytes)
        raw = self._llm.extract_fields(extraction.text)
        result = self._validator.validate(dict(raw))
        return result, extraction.path
