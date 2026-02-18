from fastapi import APIRouter, Depends

from app.core.security import verify_api_key

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("/extract")
async def extract() -> None:
    pass
