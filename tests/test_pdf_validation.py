from httpx import AsyncClient

from tests.conftest import TEST_API_KEY, make_pdf_bytes


async def test_upload_non_pdf_content_type_returns_400(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/extract",
        files={"file": ("invoice.png", b"PNG data", "image/png")},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 400


async def test_upload_oversized_file_returns_413(client: AsyncClient) -> None:
    large_content = b"%PDF" + b"x" * (11 * 1024 * 1024)
    response = await client.post(
        "/api/v1/extract",
        files={"file": ("big.pdf", large_content, "application/pdf")},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 413


async def test_upload_fake_pdf_wrong_magic_bytes_returns_400(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/extract",
        files={"file": ("fake.pdf", b"NOTPDF content here", "application/pdf")},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 400


async def test_valid_pdf_passes_all_checks(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/extract",
        files={"file": ("invoice.pdf", make_pdf_bytes(), "application/pdf")},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 200
