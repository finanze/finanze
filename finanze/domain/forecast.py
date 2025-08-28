from datetime import date
from typing import Optional
from uuid import UUID

from domain.dezimal import Dezimal
from domain.global_position import EntitiesPosition
from pydantic.dataclasses import dataclass


@dataclass
class ForecastRequest:
    target_date: date
    entities: Optional[list[UUID]] = None
    excluded_entities: Optional[list[UUID]] = None
    avg_annual_market_increase: Optional[Dezimal] = None
    avg_annual_crypto_increase: Optional[Dezimal] = None
    avg_annual_commodity_increase: Optional[Dezimal] = None


@dataclass
class CashDelta:
    currency: str
    amount: Dezimal


@dataclass
class RealEstateEquityForecast:
    id: UUID
    equity_now: Optional[Dezimal]
    equity_at_target: Optional[Dezimal]
    principal_outstanding_now: Optional[Dezimal]
    principal_outstanding_at_target: Optional[Dezimal]
    currency: str


@dataclass
class ForecastResult:
    target_date: date
    positions: EntitiesPosition
    cash_delta: list[CashDelta]
    real_estate: list[RealEstateEquityForecast]
    crypto_appreciation: Dezimal
    commodity_appreciation: Dezimal
