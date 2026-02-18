from conftest import TEST_API_KEY
from httpx import AsyncClient


async def test_extract_without_api_key_returns_401(client: AsyncClient) -> None:
    response = await client.post("/api/v1/extract")
    assert response.status_code == 401


async def test_extract_with_wrong_api_key_returns_401(client: AsyncClient) -> None:
    response = await client.post("/api/v1/extract", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


async def test_extract_with_empty_api_key_returns_401(client: AsyncClient) -> None:
    response = await client.post("/api/v1/extract", headers={"X-API-Key": ""})
    assert response.status_code == 401


async def test_extract_with_correct_api_key_passes_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/extract",
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 200
