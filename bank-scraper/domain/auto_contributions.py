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


@dataclass
class PeriodicContribution:
    id: UUID
    alias: Optional[str]
    isin: str
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
