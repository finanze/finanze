import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from domain.entity_login import EntityLoginParams, EntityLoginResult, LoginResultCode
from domain.dezimal import Dezimal
from domain.global_position import ProductType
from domain.public_keychain import PublicKeychain
from infrastructure.client.entity.exchange.polymarket.polymarket_fetcher import (
    PolymarketFetcher,
)


@pytest.fixture
def login_params():
    return EntityLoginParams(
        credentials={"identifier": "wallet"},
        keychain=PublicKeychain({}),
    )


@pytest.mark.asyncio
async def test_get_pnl_history_maps_client_data(login_params):
    client = AsyncMock()
    client.setup.return_value = EntityLoginResult(LoginResultCode.CREATED)
    client.wallet_address = "0xabc"
    client.profile = {"name": "Trader"}
    client.get_user_pnl.return_value = [{"t": 1, "p": "10.5"}]

    with patch(
        "infrastructure.client.entity.exchange.polymarket.polymarket_fetcher.PolymarketClient",
        return_value=client,
    ):
        result = await PolymarketFetcher().get_pnl_history(login_params, interval="1w")

    assert result is not None
    assert result.wallet_address == "0xabc"
    assert result.currency == "USDC"
    assert result.pnl_history[0].timestamp == 1
    assert result.pnl_history[0].currency == "USDC"
    assert str(result.pnl_history[0].value) == "10.5"
    client.get_user_pnl.assert_awaited_once_with(interval="1w")


@pytest.mark.asyncio
async def test_get_closed_positions_maps_client_data(login_params):
    client = AsyncMock()
    client.setup.return_value = EntityLoginResult(LoginResultCode.CREATED)
    client.wallet_address = "0xdef"
    client.profile = None
    client.get_closed_positions.return_value = [
        {
            "title": "Market",
            "slug": "market-1",
            "eventSlug": "event-1",
            "conditionId": "condition-1",
            "asset": "token-1",
            "icon": "https://example.com/market.png",
            "realizedPnl": "42",
            "timestamp": 1700000000,
        }
    ]
    client.get_positions.return_value = []

    with patch(
        "infrastructure.client.entity.exchange.polymarket.polymarket_fetcher.PolymarketClient",
        return_value=client,
    ):
        result = await PolymarketFetcher().get_closed_positions(login_params)

    assert result is not None
    assert result.currency == "USDC"
    position = result.closed_positions[0]
    assert position.currency == "USDC"
    assert position.name == "Market"
    assert position.market_key == "condition-1"
    assert position.event_key == "event-1"
    assert position.outcome_key == "token-1"
    assert position.market_url == "https://polymarket.com/event/event-1/market-1"
    assert position.icon_url == "https://example.com/market.png"
    assert str(result.closed_positions[0].realized_pnl) == "42"
    assert position.closed_at == "2023-11-14T22:13:20+00:00"


@pytest.mark.asyncio
async def test_get_closed_positions_includes_redeemable_positions_from_open_endpoint(
    login_params,
):
    client = AsyncMock()
    client.setup.return_value = EntityLoginResult(LoginResultCode.CREATED)
    client.wallet_address = "0xdef"
    client.profile = None
    client.get_closed_positions.return_value = []
    client.get_positions.return_value = [
        {
            "title": "Resolved loss",
            "slug": "resolved-loss",
            "eventSlug": "resolved-event",
            "conditionId": "condition-1",
            "asset": "token-1",
            "size": "40",
            "avgPrice": "0.25",
            "initialValue": "10",
            "currentValue": "0",
            "cashPnl": "-10",
            "realizedPnl": "0",
            "redeemable": True,
        }
    ]

    with patch(
        "infrastructure.client.entity.exchange.polymarket.polymarket_fetcher.PolymarketClient",
        return_value=client,
    ):
        result = await PolymarketFetcher().get_closed_positions(login_params)

    assert result is not None
    assert len(result.closed_positions) == 1
    assert result.closed_positions[0].name == "Resolved loss"
    assert str(result.closed_positions[0].realized_pnl) == "-10"


@pytest.mark.asyncio
async def test_global_position_maps_market_forecast_icon_and_pnl():
    client = AsyncMock()
    client.get_positions.return_value = [
        {
            "size": "10",
            "avgPrice": "0.4",
            "currentValue": "5",
            "initialValue": "4",
            "cashPnl": "1",
            "curPrice": "0.7",
            "title": "Market",
            "slug": "market-1",
            "eventSlug": "event-1",
            "conditionId": "condition-1",
            "asset": "token-1",
            "icon": "https://example.com/market.png",
        }
    ]
    client.get_available_balance.return_value = (0, "USDC")

    with patch(
        "infrastructure.client.entity.exchange.polymarket.polymarket_fetcher.PolymarketClient",
        return_value=client,
    ):
        result = await PolymarketFetcher().global_position()

    position = result.products[ProductType.MARKET_FORECAST].entries[0]
    assert position.currency == "USDC"
    assert position.icon_url == "https://example.com/market.png"
    assert position.market_key == "condition-1"
    assert position.event_key == "event-1"
    assert position.outcome_key == "token-1"
    assert position.market_url == "https://polymarket.com/event/event-1/market-1"
    assert str(position.mark_price) == "0.7"
    assert str(position.unrealized_pnl) == "1"


@pytest.mark.asyncio
async def test_global_position_excludes_redeemable_resolved_positions():
    client = AsyncMock()
    client.get_positions.return_value = [
        {
            "size": "40",
            "avgPrice": "0.25",
            "currentValue": "0",
            "initialValue": "10",
            "cashPnl": "-10",
            "curPrice": "0",
            "redeemable": True,
            "title": "Resolved loss",
        },
        {
            "size": "5",
            "avgPrice": "0.4",
            "currentValue": "2",
            "initialValue": "2",
            "cashPnl": "0",
            "curPrice": "0.4",
            "redeemable": False,
            "title": "Open market",
        },
    ]
    client.get_available_balance.return_value = (0, "USDC")

    with patch(
        "infrastructure.client.entity.exchange.polymarket.polymarket_fetcher.PolymarketClient",
        return_value=client,
    ):
        result = await PolymarketFetcher().global_position()

    positions = result.products[ProductType.MARKET_FORECAST].entries
    assert [position.name for position in positions] == ["Open market"]


def test_map_trade_keeps_usdc_amount_and_price_semantics():
    transaction = PolymarketFetcher()._map_trade(
        {
            "side": "BUY",
            "size": "325.379602",
            "price": "0.9219999999",
            "usdcSize": "300",
            "timestamp": 1700000000,
            "conditionId": "condition-1",
        }
    )

    assert transaction.currency == "USDC"
    assert str(transaction.amount) == "300"
    assert str(transaction.net_amount) == "300"
    assert str(transaction.size) == "325.379602"
    assert str(transaction.price) == "0.9219999999"


@pytest.mark.asyncio
async def test_market_forecast_methods_return_none_when_login_fails(login_params):
    client = AsyncMock()
    client.setup.return_value = EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)

    with patch(
        "infrastructure.client.entity.exchange.polymarket.polymarket_fetcher.PolymarketClient",
        return_value=client,
    ):
        fetcher = PolymarketFetcher()
        assert await fetcher.get_pnl_history(login_params) is None
        assert await fetcher.get_closed_positions(login_params) is None


@pytest.mark.asyncio
async def test_global_position_keeps_client_isolated_between_concurrent_logins():
    fallback_client = AsyncMock()
    client_count = 0

    def create_client():
        nonlocal client_count
        client_count += 1
        if client_count == 1:
            return fallback_client

        marker = f"account-{client_count - 1}"
        client = AsyncMock()

        async def setup(_login_params):
            await asyncio.sleep(0)
            return EntityLoginResult(LoginResultCode.CREATED)

        client.setup.side_effect = setup
        client.get_positions.return_value = [
            {
                "size": "1",
                "avgPrice": "0.5",
                "currentValue": "1",
                "initialValue": "0.5",
                "cashPnl": "0.5",
                "title": marker,
            }
        ]
        client.get_available_balance.return_value = (Dezimal("0"), "USDC")
        return client

    params = [
        EntityLoginParams(
            credentials={"identifier": "first"}, keychain=PublicKeychain({})
        ),
        EntityLoginParams(
            credentials={"identifier": "second"}, keychain=PublicKeychain({})
        ),
    ]

    with patch(
        "infrastructure.client.entity.exchange.polymarket.polymarket_fetcher.PolymarketClient",
        side_effect=create_client,
    ):
        fetcher = PolymarketFetcher()

        async def fetch_account(login_params):
            await fetcher.login(login_params)
            result = await fetcher.global_position()
            return result.products[ProductType.MARKET_FORECAST].entries[0].name

        names = await asyncio.gather(*(fetch_account(param) for param in params))

    assert names == ["account-1", "account-2"]
