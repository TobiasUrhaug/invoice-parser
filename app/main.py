import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.api.v1.router import router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.llm_extractor import LLMExtractor, init_model
from app.services.pdf_extractor import SmartPDFExtractor
from app.services.pipeline import Pipeline
from app.services.validator import InvoiceValidator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    application.state.model_loaded = False
    settings = get_settings()
    configure_logging(settings.log_level)
    try:
        llm = LLMExtractor(
            init_model(
                model_dir=settings.model_dir,
                repo_id=settings.model_repo_id,
                filename=settings.model_filename,
                n_ctx=settings.model_n_ctx,
                n_gpu_layers=settings.model_n_gpu_layers,
            )
        )
        application.state.pipeline = Pipeline(
            pdf=SmartPDFExtractor(settings.min_text_chars_per_page),
            llm=llm,
            validator=InvoiceValidator(),
        )
        application.state.model_loaded = True
    except Exception:
        logger.exception("Failed to load model during startup")
        raise
    yield


app = FastAPI(title="Invoice Parser", lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse({"error": str(exc)}, status_code=422)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse({"error": "Internal processing failure"}, status_code=500)


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
