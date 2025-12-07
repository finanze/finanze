from datetime import date
from enum import Enum
from typing import Optional
from uuid import UUID

from domain.auto_contributions import (
    ContributionTargetSubtype,
    ContributionTargetType,
)
from domain.dezimal import Dezimal
from pydantic.dataclasses import dataclass

from domain.global_position import ProductType


class MoneyEventType(str, Enum):
    CONTRIBUTION = "CONTRIBUTION"
    PERIODIC_FLOW = "PERIODIC_FLOW"
    PENDING_FLOW = "PENDING_FLOW"
    MATURITY = "MATURITY"


class MoneyEventFrequency(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    BIWEEKLY = "BIWEEKLY"
    MONTHLY = "MONTHLY"
    EVERY_TWO_MONTHS = "EVERY_TWO_MONTHS"
    EVERY_FOUR_MONTHS = "EVERY_FOUR_MONTHS"
    QUARTERLY = "QUARTERLY"
    SEMIANNUAL = "SEMIANNUAL"
    YEARLY = "YEARLY"


@dataclass
class PeriodicContributionDetails:
    target_type: ContributionTargetType
    target_subtype: Optional[ContributionTargetSubtype]
    target: str
    target_name: Optional[str]


@dataclass
class MoneyEvent:
    id: Optional[UUID]
    name: str
    amount: Dezimal
    currency: str
    date: date
    type: MoneyEventType
    frequency: Optional[MoneyEventFrequency] = None
    icon: Optional[str] = None
    details: Optional[PeriodicContributionDetails] = None
    product_type: Optional[ProductType] = None


@dataclass
class MoneyEventQuery:
    from_date: date
    to_date: date


@dataclass
class MoneyEvents:
    events: list[MoneyEvent]
