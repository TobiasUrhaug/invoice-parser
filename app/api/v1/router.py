from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.core.config import get_settings
from app.core.security import verify_api_key
from app.services.pdf_extractor import (
    FileTooLargeError,
    InvalidContentTypeError,
    InvalidMagicBytesError,
    validate_pdf,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("/extract")
async def extract(file: UploadFile) -> None:
    settings = get_settings()
    file_bytes = await file.read()
    try:
        validate_pdf(file.content_type, file_bytes, settings.max_file_size_mb)
    except InvalidContentTypeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileTooLargeError as e:
        raise HTTPException(status_code=413, detail=str(e)) from e
    except InvalidMagicBytesError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
