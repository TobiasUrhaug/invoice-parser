# Code Review Comments

Date: 2026-02-18

## Overall

The project skeleton is clean — FastAPI structure, settings, and security primitives are sensible. But the tests have issues that should be fixed before building more on top of them.

---

## `tests/conftest.py` — API key not controlled

```python
@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
```

`get_settings()` is cached with `@lru_cache`. The `API_KEY` it reads depends entirely on whatever env var exists when the first test runs. There is no fixture that sets a known `API_KEY` for tests. This makes tests environment-dependent — they may pass locally (if `API_KEY=test` happens to be set) and silently fail or behave differently in CI.

**Fix:** Override settings in the fixture, or use `monkeypatch`/`unittest.mock.patch` to inject a known API key before constructing the client. Also consider clearing the `lru_cache` between test sessions to prevent state leaking across tests.

---

## `tests/test_auth.py` — Hardcoded key, weak assertion, misleading comment

```python
async def test_extract_with_correct_api_key_passes_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/extract",
        headers={"X-API-Key": "test"},
    )
    # Auth passes — 422 because no file was sent, not 401
    assert response.status_code != 401
```

Three problems here:

1. **Hardcoded `"test"` key.** This only works if the environment has `API_KEY=test`. The test doesn't establish that precondition — it silently relies on it. See conftest issue above.

2. **`!= 401` is a very weak assertion.** A `500` or `200` would also satisfy it. The test name says "passes auth" but doesn't verify what actually happens after auth succeeds. Assert the exact expected status code. Currently the endpoint is a stub returning `None`, so FastAPI returns `200`.

3. **The comment says `422` but the endpoint returns `200`.** The `/extract` route is:
   ```python
   @router.post("/extract")
   async def extract() -> None:
       pass
   ```
   FastAPI returns `200` with a `null` body, not `422`. The comment describes future behavior (file validation not yet implemented) but reads as describing current behavior. Remove or correct it.

---

## Redundant `@pytest.mark.asyncio` decorators

`pyproject.toml` sets:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

With `auto` mode, all async test functions are treated as asyncio tests automatically. The `@pytest.mark.asyncio` decorators on every test are redundant and can be removed.

---

## `app/core/security.py` — Empty header not explicitly tested

```python
async def verify_api_key(x_api_key: str = Header(default="")) -> None:
```

A missing header and an empty `X-API-Key: ""` header are two distinct cases. Both should be rejected, but there is currently no test covering the empty-string case. Add a test for it.

---

## `app/main.py` — `model_loaded` never becomes `True`

```python
@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    application.state.model_loaded = False
    yield
```

The health endpoint exposes `model_loaded`, but there is no code path that sets it to `True`. This is expected at the current stage, but the health test only covers the startup state. Once model loading is implemented, a test should verify that the field reflects actual model state.

---

## Missing test coverage for existing code

| Scenario | Covered? |
|---|---|
| Health returns `model_loaded: false` at startup | Yes |
| `model_loaded` becomes `true` when model loads | No (not yet implemented) |
| No `X-API-Key` header → 401 | Yes |
| Wrong `X-API-Key` value → 401 | Yes |
| Correct `X-API-Key` → not 401 | Yes (but fragile — see above) |
| Empty string `X-API-Key: ""` → 401 | No |
| App fails to start when `API_KEY` env var is missing | No |

---

## Priority

Fix the conftest isolation issue first. All auth tests are built on top of it, and until it is addressed the test suite cannot be trusted to produce reliable results in any environment other than your own machine.
