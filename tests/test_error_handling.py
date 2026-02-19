from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient


def _make_app_with_error_route() -> FastAPI:
    """Return a minimal app with error handlers and a route that raises."""
    from app.main import app as main_app

    test_app = FastAPI()
    for exc_cls, handler in main_app.exception_handlers.items():
        test_app.add_exception_handler(exc_cls, handler)  # type: ignore[arg-type]

    @test_app.get("/boom")
    async def _boom() -> None:
        raise RuntimeError("internal detail")

    return test_app


def test_unhandled_exception_returns_500_error_envelope() -> None:
    """Unhandled exceptions return 500 with {"error": ...}, not {"detail": ...}."""
    test_app = _make_app_with_error_route()
    with TestClient(test_app, raise_server_exceptions=False) as c:
        response = c.get("/boom")
    assert response.status_code == 500
    body = response.json()
    assert "error" in body
    assert "detail" not in body
    assert "internal detail" not in body["error"]


async def test_http_exception_uses_error_envelope(client: AsyncClient) -> None:
    """HTTPException responses must use {"error": detail} shape."""
    response = await client.post(
        "/api/v1/extract",
        headers={"X-API-Key": "test-api-key"},
        files={"file": ("invoice.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 400
    body = response.json()
    assert "error" in body
    assert "detail" not in body
