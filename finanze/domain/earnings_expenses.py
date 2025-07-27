from datetime import date
from enum import Enum
from typing import Optional
from uuid import UUID

from domain.dezimal import Dezimal
from pydantic.dataclasses import dataclass


class FlowFrequency(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    EVERY_TWO_MONTHS = "EVERY_TWO_MONTHS"
    QUARTERLY = "QUARTERLY"
    EVERY_FOUR_MONTHS = "EVERY_FOUR_MONTHS"
    SEMIANNUALLY = "SEMIANNUALLY"
    YEARLY = "YEARLY"


class FlowType(str, Enum):
    EARNING = "EARNING"
    EXPENSE = "EXPENSE"


@dataclass
class PeriodicFlow:
    id: Optional[UUID]
    name: str
    amount: Dezimal
    currency: str
    flow_type: FlowType
    frequency: FlowFrequency
    category: Optional[str]
    enabled: bool
    since: date
    until: Optional[date]
    next_date: Optional[date] = None


@dataclass
class PendingFlow:
    id: Optional[UUID]
    name: str
    amount: Dezimal
    currency: str
    flow_type: FlowType
    category: Optional[str]
    enabled: bool
    date: Optional[date]
