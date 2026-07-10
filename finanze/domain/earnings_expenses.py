from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from domain.dezimal import Dezimal
from pydantic.dataclasses import dataclass


class FlowStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    COMPLETED = "COMPLETED"


class FlowFrequency(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    BIWEEKLY = "BIWEEKLY"
    SEMIMONTHLY = "SEMIMONTHLY"
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
class RealEstateFlowInfo:
    flow_subtype: str
    linked_loan_hash: Optional[str] = None


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
    icon: Optional[str]
    linked: Optional[bool] = None
    real_estate_flow: Optional[RealEstateFlowInfo] = None
    next_date: Optional[date] = None
    max_amount: Optional[Dezimal] = None


@dataclass
class PendingFlow:
    id: Optional[UUID]
    name: str
    amount: Dezimal
    currency: str
    flow_type: FlowType
    category: Optional[str]
    status: FlowStatus
    date: Optional[date]
    icon: Optional[str]
    status_changed_at: Optional[datetime] = None


class FlowSortField(str, Enum):
    AMOUNT = "amount"
    DATE = "date"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


@dataclass
class PendingFlowQuery:
    statuses: Optional[list[FlowStatus]] = None
    flow_type: Optional[FlowType] = None
    categories: Optional[list[str]] = None
    sort_by: FlowSortField = FlowSortField.AMOUNT
    order: SortOrder = SortOrder.DESC
    page: Optional[int] = None
    limit: Optional[int] = None
    include_stats: bool = False
    include_categories: bool = False


@dataclass
class CategoryStat:
    category: Optional[str]
    amounts: dict[str, Dezimal]
    name: Optional[str] = None


@dataclass
class FlowTypeStat:
    totals: dict[str, Dezimal]
    by_category: list[CategoryStat]
    count: int


@dataclass
class PendingFlowStats:
    earning: FlowTypeStat
    expense: FlowTypeStat


@dataclass
class PendingFlowPage:
    entries: list[PendingFlow]
    total: int
    page: Optional[int]
    limit: Optional[int]
    has_more: bool
    stats: Optional[PendingFlowStats] = None
    categories: Optional[list[str]] = None
