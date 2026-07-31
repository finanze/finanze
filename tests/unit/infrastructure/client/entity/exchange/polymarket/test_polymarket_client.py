import asyncio
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from domain.entity_login import EntityLoginParams
from domain.public_keychain import PublicKeychain
from infrastructure.client.entity.exchange.polymarket.polymarket_client import (
    CLOSED_POSITIONS_CACHE_TTL,
    PNL_CACHE_TTL,
    PolymarketClient,
)


@pytest.fixture
def login_params():
    return EntityLoginParams(
        credentials={"identifier": "0x0000000000000000000000000000000000000001"},
        keychain=PublicKeychain({}),
    )


@pytest_asyncio.fixture(autouse=True)
async def clear_polymarket_caches():
    await PolymarketClient.get_closed_positions.cache.clear()
    await PolymarketClient.get_user_pnl.cache.clear()
    yield
    await PolymarketClient.get_closed_positions.cache.clear()
    await PolymarketClient.get_user_pnl.cache.clear()


async def _setup_client(login_params):
    client = PolymarketClient()
    client.get_public_profile = AsyncMock(return_value={"name": "Trader"})
    await client.setup(login_params)
    return client


@pytest.mark.asyncio
async def test_closed_positions_cache_is_shared_by_clients(login_params, monkeypatch):
    first_client = await _setup_client(login_params)
    second_client = await _setup_client(login_params)
    first_client._session.get = AsyncMock()
    first_client._session.get.return_value.raise_for_status = lambda: None
    first_client._session.get.return_value.json = AsyncMock(
        return_value=[{"slug": "market-1"}]
    )
    second_client._session.get = first_client._session.get
    cache_set = AsyncMock(wraps=PolymarketClient.get_closed_positions.cache.set)
    monkeypatch.setattr(PolymarketClient.get_closed_positions.cache, "set", cache_set)

    assert await first_client.get_closed_positions() == [{"slug": "market-1"}]
    assert await second_client.get_closed_positions() == [{"slug": "market-1"}]

    first_client._session.get.assert_awaited_once()
    assert cache_set.await_args.kwargs["ttl"] == CLOSED_POSITIONS_CACHE_TTL


@pytest.mark.asyncio
async def test_closed_positions_cache_refreshes_after_expiry(login_params, monkeypatch):
    client = await _setup_client(login_params)
    get = AsyncMock()
    response = get.return_value
    response.raise_for_status = lambda: None
    response.json = AsyncMock(
        side_effect=[[{"slug": "market-1"}], [{"slug": "market-2"}]]
    )
    client._session.get = get

    cache = PolymarketClient.get_closed_positions.cache
    original_set = cache.set

    async def set_with_short_ttl(key, value, ttl=None):
        return await original_set(key, value, ttl=0.01)

    monkeypatch.setattr(cache, "set", set_with_short_ttl)

    assert await client.get_closed_positions() == [{"slug": "market-1"}]
    await asyncio.sleep(0.02)
    assert await client.get_closed_positions() == [{"slug": "market-2"}]
    assert get.await_count == 2


@pytest.mark.asyncio
async def test_pnl_cache_is_separated_by_wallet_and_interval(login_params, monkeypatch):
    first_client = await _setup_client(login_params)
    second_client = await _setup_client(login_params)
    second_client._wallet_address = "0x0000000000000000000000000000000000000002"
    get = AsyncMock()

    response = get.return_value
    response.raise_for_status = lambda: None
    response.json = AsyncMock(side_effect=[[{"t": 1, "p": "10"}]] * 3)
    first_client._session.get = get
    second_client._session.get = get
    cache_set = AsyncMock(wraps=PolymarketClient.get_user_pnl.cache.set)
    monkeypatch.setattr(PolymarketClient.get_user_pnl.cache, "set", cache_set)

    assert await first_client.get_user_pnl(interval="1d") == [{"t": 1, "p": "10"}]
    assert await first_client.get_user_pnl(interval="1w") == [{"t": 1, "p": "10"}]
    assert await second_client.get_user_pnl(interval="1d") == [{"t": 1, "p": "10"}]
    assert await second_client.get_user_pnl(interval="1d") == [{"t": 1, "p": "10"}]

    assert get.await_count == 3
    assert cache_set.await_args.kwargs["ttl"] == PNL_CACHE_TTL
