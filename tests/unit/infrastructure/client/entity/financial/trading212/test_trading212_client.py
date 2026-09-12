import base64
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from domain.entity_login import LoginResultCode
from infrastructure.client.entity.financial.trading212.trading212_client import (
    Trading212Client,
)


class FakeResponse:
    def __init__(self, status, body=None, headers=None, text=""):
        self.status = status
        self.ok = 200 <= status < 300
        self.headers = headers or {}
        self._body = body if body is not None else {}
        self._text = text

    async def json(self):
        return self._body

    async def text(self):
        return self._text

    def raise_for_status(self):
        if self.ok:
            return
        raise httpx.HTTPStatusError(
            message=str(self.status),
            request=httpx.Request("GET", "https://demo.trading212.com"),
            response=httpx.Response(self.status),
        )


def _client():
    with patch(
        "infrastructure.client.entity.financial.trading212.trading212_client.new_http_session"
    ) as mocked:
        session = AsyncMock()
        mocked.return_value = session
        client = Trading212Client()
        client._session = session
        return client


@pytest.mark.asyncio
async def test_set_auth_uses_basic_header():
    client = _client()
    client._set_auth("key", "secret")
    encoded = base64.b64encode(b"key:secret").decode("utf-8")
    assert client._headers["Authorization"] == f"Basic {encoded}"


@pytest.mark.asyncio
async def test_setup_missing_credentials():
    client = _client()
    result = await client.setup(None, "secret")
    assert result.code == LoginResultCode.INVALID_CREDENTIALS


@pytest.mark.asyncio
async def test_setup_unauthorized():
    client = _client()
    client.get_account_summary = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            message="401",
            request=httpx.Request("GET", "https://demo.trading212.com"),
            response=httpx.Response(401),
        )
    )
    result = await client.setup("key", "secret")
    assert result.code == LoginResultCode.INVALID_CREDENTIALS


@pytest.mark.asyncio
async def test_setup_success_sets_auth():
    client = _client()
    client.get_account_summary = AsyncMock(return_value={"id": 1})
    result = await client.setup("key", "secret")
    assert result.code == LoginResultCode.CREATED
    encoded = base64.b64encode(b"key:secret").decode("utf-8")
    assert client._headers["Authorization"] == f"Basic {encoded}"


@pytest.mark.asyncio
async def test_get_retries_on_429(monkeypatch):
    client = _client()
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(
        "infrastructure.client.entity.financial.trading212.trading212_client.asyncio.sleep",
        fake_sleep,
    )
    monkeypatch.setattr(
        "infrastructure.client.entity.financial.trading212.trading212_client.random.uniform",
        lambda _a, _b: 0,
    )
    client._session.get = AsyncMock(
        side_effect=[
            FakeResponse(429, headers={"Retry-After": "7"}),
            FakeResponse(200, body={"id": 1}),
        ]
    )
    result = await client._get("/api/v0/equity/account/summary")
    assert result == {"id": 1}
    assert slept == [7]


@pytest.mark.asyncio
async def test_get_retries_on_429_without_zero_wait(monkeypatch):
    client = _client()
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(
        "infrastructure.client.entity.financial.trading212.trading212_client.asyncio.sleep",
        fake_sleep,
    )
    monkeypatch.setattr(
        "infrastructure.client.entity.financial.trading212.trading212_client.random.uniform",
        lambda _a, _b: 0,
    )
    client._session.get = AsyncMock(
        side_effect=[
            FakeResponse(429, headers={"Retry-After": "0", "x-ratelimit-reset": "1"}),
            FakeResponse(429, headers={"x-ratelimit-reset": "1"}),
            FakeResponse(200, body={"id": 1}),
        ]
    )
    result = await client._get("/api/v0/equity/account/summary")
    assert result == {"id": 1}
    assert slept == [2.0, 4.0]
    assert all(delay > 0 for delay in slept)


@pytest.mark.asyncio
async def test_get_account_summary_reuses_recent_response():
    client = _client()
    client._session.get = AsyncMock(return_value=FakeResponse(200, body={"id": 1}))
    first = await client.get_account_summary()
    second = await client.get_account_summary()
    assert first == {"id": 1}
    assert second == first
    assert client._session.get.await_count == 1


@pytest.mark.asyncio
async def test_iter_pages_follows_next_page_path():
    client = _client()
    client._get = AsyncMock(
        side_effect=[
            {
                "items": [{"id": 1}],
                "nextPagePath": "/api/v0/equity/history/orders?cursor=abc",
            },
            {"items": [{"id": 2}], "nextPagePath": None},
        ]
    )
    pages = [page async for page in client.iter_pages("/api/v0/equity/history/orders")]
    assert pages == [[{"id": 1}], [{"id": 2}]]
    assert client._get.await_args_list[0].args == (
        "/api/v0/equity/history/orders?limit=50",
    )
    assert client._get.await_args_list[1].args == (
        "/api/v0/equity/history/orders?cursor=abc",
    )


@pytest.mark.asyncio
async def test_to_path_strips_host_from_absolute_url():
    path = Trading212Client._to_path(
        "https://demo.trading212.com/api/v0/equity/history/orders?cursor=xyz"
    )
    assert path == "/api/v0/equity/history/orders?cursor=xyz"


@pytest.mark.asyncio
async def test_get_instruments_is_cached():
    client = _client()
    cache = getattr(Trading212Client.get_instruments, "cache", None)
    if cache is not None:
        await cache.clear()
    client._session.get = AsyncMock(
        return_value=FakeResponse(200, body=[{"ticker": "AAPL_US_EQ"}])
    )
    first = await client.get_instruments()
    second = await client.get_instruments()
    assert first == [{"ticker": "AAPL_US_EQ"}]
    assert second == first
    assert client._session.get.await_count == 1
    if cache is not None:
        await cache.clear()
