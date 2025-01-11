from datetime import date
from enum import Enum
from typing import Optional

from pydantic.dataclasses import dataclass


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
    alias: str
    isin: str
    amount: float
    since: date
    until: Optional[date]
    frequency: ContributionFrequency
    active: bool


@dataclass
class AutoContributions:
    periodic: list[PeriodicContribution]
