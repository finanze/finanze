from typing import Any
from uuid import UUID

from domain.dezimal import Dezimal
from pydantic.dataclasses import dataclass


@dataclass
class MarketForecastPnlPoint:
    timestamp: int
    value: Dezimal
    entity_account_id: UUID | None = None
    wallet_address: str | None = None


@dataclass
class MarketForecastClosedPosition:
    entity_account_id: UUID | None = None
    wallet_address: str | None = None
    title: str | None = None
    slug: str | None = None
    event_slug: str | None = None
    icon: str | None = None
    outcome: str | None = None
    condition_id: str | None = None
    asset: str | None = None
    size: Dezimal | None = None
    avg_price: Dezimal | None = None
    price: Dezimal | None = None
    initial_value: Dezimal | None = None
    current_value: Dezimal | None = None
    cash_pnl: Dezimal | None = None
    percent_pnl: Dezimal | None = None
    cur_price: Dezimal | None = None
    redemption_value: Dezimal | None = None
    end_date: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    closed_at: str | None = None
    realized_pnl: Dezimal | None = None
    total_bought: Dezimal | None = None
    total_sold: Dezimal | None = None


@dataclass
class MarketForecastPnlAccountData:
    wallet_address: str
    profile: dict[str, Any] | None = None
    pnl_history: list[MarketForecastPnlPoint] | None = None


@dataclass
class MarketForecastClosedPositionsAccountData:
    wallet_address: str
    profile: dict[str, Any] | None = None
    closed_positions: list[MarketForecastClosedPosition] | None = None


@dataclass
class MarketForecastAccountSummary:
    entity_account_id: UUID
    entity_id: UUID
    account_name: str | None
    wallet_address: str
    profile: dict[str, Any] | None


@dataclass
class MarketForecastPnlAccount(MarketForecastAccountSummary):
    pnl_history: list[MarketForecastPnlPoint]


@dataclass
class MarketForecastClosedPositionsAccount(MarketForecastAccountSummary):
    closed_positions: list[MarketForecastClosedPosition]


@dataclass
class MarketForecastPnlResponse:
    interval: str
    accounts: list[MarketForecastPnlAccount]
    pnl_history: list[MarketForecastPnlPoint]


@dataclass
class MarketForecastClosedPositionsResponse:
    accounts: list[MarketForecastClosedPositionsAccount]
    closed_positions: list[MarketForecastClosedPosition]
