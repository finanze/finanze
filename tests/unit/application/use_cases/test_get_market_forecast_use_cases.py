from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import TypeAdapter

from application.use_cases.get_market_forecast_closed_positions import (
    GetMarketForecastClosedPositionsImpl,
)
from application.use_cases.get_market_forecast_pnl import GetMarketForecastPnlImpl
from domain.entity_account import EntityAccount
from domain.market_forecast import (
    MarketForecastClosedPositionsAccountData,
    MarketForecastClosedPosition,
    MarketForecastPnlAccountData,
    MarketForecastPnlPoint,
    MarketForecastPnlResponse,
)
from domain.native_entities import POLYMARKET


def _account(name: str = "Main") -> EntityAccount:
    return EntityAccount(
        id=uuid4(),
        entity_id=POLYMARKET.id,
        created_at=datetime.utcnow(),
        name=name,
    )


@pytest.mark.asyncio
async def test_get_market_forecast_pnl_returns_aggregated_history():
    account = _account()
    entity_account_port = AsyncMock()
    entity_account_port.get_by_entity_id.return_value = [account]
    credentials_port = AsyncMock()
    credentials_port.get.return_value = {"identifier": "wallet"}
    provider = AsyncMock()
    provider.get_pnl_history.return_value = MarketForecastPnlAccountData(
        wallet_address="0xabc",
        currency="USDC",
        profile={"name": "Trader"},
        pnl_history=[
            MarketForecastPnlPoint(timestamp=1, value=10, currency="USDC"),
            MarketForecastPnlPoint(timestamp=2, value=12, currency="USDC"),
        ],
    )

    uc = GetMarketForecastPnlImpl(
        entity_account_port=entity_account_port,
        credentials_port=credentials_port,
        provider=provider,
    )

    result = await uc.execute(interval="all")

    assert result.interval == "all"
    assert len(result.accounts) == 1
    assert result.accounts[0].entity_account_id == account.id
    assert result.accounts[0].wallet_address == "0xabc"
    assert result.accounts[0].currency == "USDC"
    assert result.accounts[0].pnl_history[0].entity_account_id == account.id
    assert result.accounts[0].pnl_history[0].currency == "USDC"
    payload = TypeAdapter(MarketForecastPnlResponse).dump_python(
        result, mode="json", by_alias=True
    )
    assert payload["pnl_history"] == payload["accounts"][0]["pnl_history"]


@pytest.mark.asyncio
async def test_get_market_forecast_closed_positions_returns_aggregated_positions():
    account = _account()
    entity_account_port = AsyncMock()
    entity_account_port.get_by_entity_id.return_value = [account]
    credentials_port = AsyncMock()
    credentials_port.get.return_value = {"identifier": "wallet"}
    provider = AsyncMock()
    provider.get_closed_positions.return_value = (
        MarketForecastClosedPositionsAccountData(
            wallet_address="0xdef",
            currency="USDC",
            profile={"name": "Closer"},
            closed_positions=[
                MarketForecastClosedPosition(
                    currency="USDC", market_key="market-1", realized_pnl=42
                )
            ],
        )
    )

    uc = GetMarketForecastClosedPositionsImpl(
        entity_account_port=entity_account_port,
        credentials_port=credentials_port,
        provider=provider,
    )

    result = await uc.execute()

    assert len(result.accounts) == 1
    assert result.accounts[0].entity_account_id == account.id
    assert result.accounts[0].currency == "USDC"
    assert result.accounts[0].closed_positions[0].entity_account_id == account.id
    assert result.accounts[0].closed_positions[0].currency == "USDC"
