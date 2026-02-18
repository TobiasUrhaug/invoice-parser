from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.v1.router import router


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    application.state.model_loaded = False
    yield


app = FastAPI(title="Invoice Parser", lifespan=lifespan)
app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {"status": "ok", "model_loaded": getattr(app.state, "model_loaded", False)}
    )
