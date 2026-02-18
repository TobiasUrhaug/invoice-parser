import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.api.v1.router import router
from app.core.config import get_settings
from app.services.llm_extractor import init_model

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    application.state.model_loaded = False
    settings = get_settings()
    try:
        application.state.llm = init_model(
            model_dir=settings.model_dir,
            repo_id=settings.model_repo_id,
            filename=settings.model_filename,
            n_ctx=settings.model_n_ctx,
            n_gpu_layers=settings.model_n_gpu_layers,
        )
        application.state.model_loaded = True
    except Exception:
        logger.exception("Failed to load model during startup")
        raise
    yield


app = FastAPI(title="Invoice Parser", lifespan=lifespan)


@app.middleware("http")
async def require_model_loaded(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if request.url.path.startswith("/api/") and not getattr(
        app.state, "model_loaded", False
    ):
        return JSONResponse(
            {"error": "Service unavailable: model is loading"},
            status_code=503,
        )
    return await call_next(request)


app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {"status": "ok", "model_loaded": getattr(app.state, "model_loaded", False)}
    )
