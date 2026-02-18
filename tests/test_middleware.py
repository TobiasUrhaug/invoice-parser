from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_api_returns_503_when_model_not_loaded() -> None:
    with patch("app.services.llm_extractor.init_model"):
        app.state.model_loaded = False
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/extract")
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_api_request_not_blocked_when_model_loaded() -> None:
    with patch("app.services.llm_extractor.init_model"):
        app.state.model_loaded = True
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/extract")
    assert response.status_code != 503


@pytest.mark.asyncio
async def test_health_not_blocked_when_model_not_loaded() -> None:
    with patch("app.services.llm_extractor.init_model"):
        app.state.model_loaded = False
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
    assert response.status_code == 200
