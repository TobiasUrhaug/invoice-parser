import hmac

from fastapi import Header, HTTPException

from app.core.config import get_settings


async def verify_api_key(x_api_key: str = Header(default="")) -> None:
    settings = get_settings()
    if not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
