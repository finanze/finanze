from datetime import date
from enum import Enum
from typing import Optional
from uuid import UUID

from domain.dezimal import Dezimal
from domain.fetch_record import DataSource
from pydantic.dataclasses import dataclass


class ContributionFrequency(str, Enum):
    WEEKLY = "WEEKLY"
    BIWEEKLY = "BIWEEKLY"
    MONTHLY = "MONTHLY"
    BIMONTHLY = "BIMONTHLY"
    EVERY_FOUR_MONTHS = "EVERY_FOUR_MONTHS"
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
    target_name: str
    target_type: ContributionTargetType
    amount: Dezimal
    currency: str
    since: date
    until: Optional[date]
    frequency: ContributionFrequency
    active: bool
    source: DataSource
    next_date: Optional[date] = None


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


@dataclass
class ManualPeriodicContribution:
    entity_id: UUID
    name: str
    target: str
    target_name: Optional[str]
    target_type: ContributionTargetType
    amount: Dezimal
    currency: str
    since: date
    until: Optional[date]
    frequency: ContributionFrequency
