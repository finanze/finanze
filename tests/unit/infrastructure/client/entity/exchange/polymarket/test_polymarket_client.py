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


def _page(rows, next_cursor=None):
    return {
        "data": rows,
        "pagination": {
            "limit": 1000,
            "has_more": bool(next_cursor),
            "next_cursor": next_cursor,
        },
    }


def _pnl(points):
    return {"data": {"proxy_wallet": "0x1", "interval": "all", "points": points}}


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
        return_value=_page([{"slug": "market-1"}])
    )
    second_client._session.get = first_client._session.get
    cache_set = AsyncMock(wraps=PolymarketClient.get_closed_positions.cache.set)
    monkeypatch.setattr(PolymarketClient.get_closed_positions.cache, "set", cache_set)

    first = await first_client.get_closed_positions()
    second = await second_client.get_closed_positions()
    assert first[0]["slug"] == "market-1"
    assert second == first

    first_client._session.get.assert_awaited_once()
    assert cache_set.await_args.kwargs["ttl"] == CLOSED_POSITIONS_CACHE_TTL


@pytest.mark.asyncio
async def test_closed_positions_cache_refreshes_after_expiry(login_params, monkeypatch):
    client = await _setup_client(login_params)
    get = AsyncMock()
    response = get.return_value
    response.raise_for_status = lambda: None
    response.json = AsyncMock(
        side_effect=[_page([{"slug": "market-1"}]), _page([{"slug": "market-2"}])]
    )
    client._session.get = get

    cache = PolymarketClient.get_closed_positions.cache
    original_set = cache.set

    async def set_with_short_ttl(key, value, ttl=None):
        return await original_set(key, value, ttl=0.01)

    monkeypatch.setattr(cache, "set", set_with_short_ttl)

    assert (await client.get_closed_positions())[0]["slug"] == "market-1"
    await asyncio.sleep(0.02)
    assert (await client.get_closed_positions())[0]["slug"] == "market-2"
    assert get.await_count == 2


@pytest.mark.asyncio
async def test_pnl_cache_is_separated_by_wallet_and_interval(login_params, monkeypatch):
    first_client = await _setup_client(login_params)
    second_client = await _setup_client(login_params)
    second_client._wallet_address = "0x0000000000000000000000000000000000000002"
    get = AsyncMock()

    response = get.return_value
    response.raise_for_status = lambda: None
    response.json = AsyncMock(
        side_effect=[_pnl([{"timestamp": 1, "trade_pnl": "10"}])] * 3
    )
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


def _get_mock(*payloads):
    get = AsyncMock()
    get.return_value.raise_for_status = lambda: None
    get.return_value.json = AsyncMock(side_effect=list(payloads))
    return get


@pytest.mark.asyncio
async def test_collection_follows_cursor_and_repeats_filters(login_params):
    client = await _setup_client(login_params)
    client._session.get = _get_mock(
        _page([{"transaction_hash": "0xa"}], next_cursor="c1"),
        _page([{"transaction_hash": "0xb"}]),
    )

    trades = await client.get_trades()

    assert [t["transactionHash"] for t in trades] == ["0xa", "0xb"]
    first_call, second_call = client._session.get.await_args_list
    assert first_call.args[0] == "https://data-api.polymarket.com/v2/trades"
    assert first_call.kwargs["params"] == {
        "user": client.wallet_address,
        "start": 1,
        "limit": 1000,
    }
    assert second_call.kwargs["params"] == {
        "user": client.wallet_address,
        "start": 1,
        "cursor": "c1",
    }


@pytest.mark.asyncio
async def test_positions_query_open_and_redeemable_statuses(login_params):
    client = await _setup_client(login_params)
    client._session.get = _get_mock(
        _page(
            [
                {
                    "condition_id": "0xc",
                    "token_id": "123",
                    "current_size": 10.0,
                    "avg_price": 0.5,
                    "entry_cost_usdc": 5.0,
                    "current_value": 6.0,
                    "unrealized_pnl": 1.0,
                    "current_price": 0.6,
                    "status": "OPEN",
                    "redeemable": False,
                    "title": "Market",
                    "slug": "market",
                    "event_slug": "event",
                    "outcome": "Yes",
                    "end_date": "2027-01-01",
                }
            ]
        ),
        _page([{"condition_id": "0xd", "status": "REDEEMABLE"}]),
        _page([{"condition_id": "0xe", "status": "REDEEMABLE_LOST"}]),
    )

    positions = await client.get_positions()

    statuses = [
        call.kwargs["params"]["status"] for call in client._session.get.await_args_list
    ]
    assert statuses == ["OPEN", "REDEEMABLE", "REDEEMABLE_LOST"]
    open_position = positions[0]
    assert open_position["conditionId"] == "0xc"
    assert open_position["asset"] == "123"
    assert open_position["size"] == 10.0
    assert open_position["avgPrice"] == 0.5
    assert open_position["initialValue"] == 5.0
    assert open_position["currentValue"] == 6.0
    assert open_position["cashPnl"] == 1.0
    assert open_position["curPrice"] == 0.6
    assert open_position["eventSlug"] == "event"
    assert open_position["endDate"] == "2027-01-01"
    assert open_position["redeemable"] is False
    assert [p["redeemable"] for p in positions[1:]] == [True, True]


@pytest.mark.asyncio
async def test_closed_positions_use_closed_status_and_lifetime_fields(login_params):
    client = await _setup_client(login_params)
    client._session.get = _get_mock(
        _page(
            [
                {
                    "condition_id": "0xc",
                    "current_size": 0.0,
                    "current_value": 0.0,
                    "avg_price": 0.75,
                    "total_size": 667.0,
                    "realized_pnl": 167.2,
                    "last_event_at": 1775397453,
                    "status": "CLOSED",
                }
            ]
        )
    )

    [closed] = await client.get_closed_positions()

    assert client._session.get.await_args.kwargs["params"]["status"] == "CLOSED"
    assert closed["realizedPnl"] == 167.2
    assert closed["totalBought"] == 667.0
    assert closed["timestamp"] == 1775397453
    assert "size" not in closed
    assert "currentValue" not in closed


@pytest.mark.asyncio
async def test_user_pnl_maps_trade_pnl_series(login_params):
    client = await _setup_client(login_params)
    client._session.get = _get_mock(
        _pnl(
            [
                {"timestamp": 1, "trade_pnl": 2.5, "economic_pnl": 9.0},
                {"timestamp": 2, "trade_pnl": None},
            ]
        )
    )

    assert await client.get_user_pnl() == [{"t": 1, "p": 2.5}]
    call = client._session.get.await_args
    assert call.args[0] == "https://data-api.polymarket.com/v2/user-pnl"
    assert call.kwargs["params"]["user"] == client.wallet_address
