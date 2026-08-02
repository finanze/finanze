from unittest.mock import AsyncMock, patch

import pytest

from domain.entity_login import EntityLoginParams, EntityLoginResult, LoginResultCode
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
        }
    ]

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
