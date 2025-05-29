from datetime import date
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic.dataclasses import dataclass

from domain.dezimal import Dezimal


class ContributionFrequency(str, Enum):
    WEEKLY = "WEEKLY"
    BIWEEKLY = "BIWEEKLY"
    MONTHLY = "MONTHLY"
    BIMONTHLY = "BIMONTHLY"
    QUARTERLY = "QUARTERLY"
    SEMIANNUAL = "SEMIANNUAL"
    YEARLY = "YEARLY"


class ContributionTargetType(str, Enum):
    STOCK_ETF = "STOCK_ETF"
    FUND = "FUND"
    FUND_PORTFOLIO = "FUND_PORTFOLIO"


@dataclass
class PeriodicContribution:
    id: UUID
    alias: Optional[str]
    target: str
    target_type: ContributionTargetType
    amount: Dezimal
    currency: str
    since: date
    until: Optional[date]
    frequency: ContributionFrequency
    active: bool
    is_real: bool


@dataclass
class AutoContributions:
    periodic: list[PeriodicContribution]


@dataclass
class EntityContributions:
    contributions: dict[str, AutoContributions]


@dataclass
class ContributionQueryRequest:
    entities: Optional[list[UUID]] = None
    excluded_entities: Optional[list[UUID]] = None
    real: Optional[bool] = None
