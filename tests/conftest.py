from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app

TEST_API_KEY = "test-api-key"


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[AsyncClient, None]:
    monkeypatch.setenv("API_KEY", TEST_API_KEY)
    get_settings.cache_clear()
    with patch("app.services.llm_extractor.init_model"):
        app.state.model_loaded = True
        app.state.pipeline = MagicMock()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    app.state.model_loaded = False
    get_settings.cache_clear()
