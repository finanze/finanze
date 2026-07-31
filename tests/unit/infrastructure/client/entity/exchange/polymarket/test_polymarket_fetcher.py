from unittest.mock import AsyncMock, patch

import pytest

from domain.entity_login import EntityLoginParams, EntityLoginResult, LoginResultCode
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
    assert result.pnl_history[0].timestamp == 1
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
            "slug": "market-1",
            "eventSlug": "event-1",
            "realizedPnl": "42",
        }
    ]

    with patch(
        "infrastructure.client.entity.exchange.polymarket.polymarket_fetcher.PolymarketClient",
        return_value=client,
    ):
        result = await PolymarketFetcher().get_closed_positions(login_params)

    assert result is not None
    assert result.closed_positions[0].slug == "market-1"
    assert result.closed_positions[0].event_slug == "event-1"
    assert str(result.closed_positions[0].realized_pnl) == "42"


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
