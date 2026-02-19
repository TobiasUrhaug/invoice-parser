import logging
import time
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from app.api.v1.schemas import InvoiceResult
from app.core.config import get_settings
from app.core.security import verify_api_key
from app.services.pdf_extractor import (
    FileTooLargeError,
    InvalidContentTypeError,
    InvalidMagicBytesError,
    validate_pdf,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])


_INVOICE_FIELDS = tuple(InvoiceResult.model_fields.keys())


def _null_fields(result: InvoiceResult) -> list[str]:
    return [f for f in _INVOICE_FIELDS if getattr(result, f) is None]


def _outcome(null: list[str]) -> Literal["success", "partial"]:
    return "partial" if null else "success"


@router.post("/extract")
async def extract(file: UploadFile, request: Request) -> JSONResponse:
    request_id = str(uuid.uuid4())
    start = time.monotonic()
    status_code = 500
    file_size_bytes: int | None = None
    outcome: str | None = None
    extraction_path: str | None = None
    null: list[str] = []

    try:
        settings = get_settings()
        file_bytes = await file.read()
        file_size_bytes = len(file_bytes)
        try:
            validate_pdf(file.content_type, file_bytes, settings.max_file_size_mb)
        except InvalidContentTypeError as e:
            status_code = 400
            raise HTTPException(status_code=400, detail=str(e)) from e
        except FileTooLargeError as e:
            status_code = 413
            raise HTTPException(status_code=413, detail=str(e)) from e
        except InvalidMagicBytesError as e:
            status_code = 400
            raise HTTPException(status_code=400, detail=str(e)) from e

        pipeline = request.app.state.pipeline
        result, extraction_path = pipeline.run(file_bytes)
        null = _null_fields(result)
        outcome = _outcome(null)
        status_code = 200
        return JSONResponse(
            result.model_dump(mode="json"),
            status_code=200,
            headers={"X-Request-Id": request_id},
        )
    finally:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "extract complete",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": str(request.url.path),
                "status_code": status_code,
                "file_size_bytes": file_size_bytes,
                "outcome": outcome,
                "extraction_path": extraction_path,
                "null_fields": null,
                "duration_ms": duration_ms,
            },
        )
