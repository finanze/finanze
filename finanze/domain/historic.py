from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.transactions import BaseInvestmentTx
from pydantic.dataclasses import dataclass


class HistoricSortBy(str, Enum):
    MATURITY = "maturity"
    LAST_INVEST_DATE = "last_invest_date"
    INVESTED = "invested"


class HistoricState(str, Enum):
    COMPLETED = "COMPLETED"
    DEFAULTED = "DEFAULTED"


FINAL_HISTORIC_STATES = {HistoricState.COMPLETED.value, HistoricState.DEFAULTED.value}


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


@dataclass(kw_only=True)
class BaseHistoricEntry:
    id: UUID
    name: str
    invested: Dezimal
    repaid: Optional[Dezimal]
    returned: Optional[Dezimal]
    currency: str
    last_invest_date: datetime
    last_tx_date: datetime
    effective_maturity: Optional[datetime]
    net_return: Optional[Dezimal]
    fees: Optional[Dezimal]
    retentions: Optional[Dezimal]
    interests: Optional[Dezimal]
    state: Optional[str]
    entity: Entity
    product_type: ProductType
    related_txs: list[BaseInvestmentTx]
    entity_account_id: Optional[UUID] = None
    source: DataSource = DataSource.REAL
    manual_key: Optional[str] = None


@dataclass(kw_only=True)
class FactoringEntry(BaseHistoricEntry):
    interest_rate: Dezimal
    gross_interest_rate: Dezimal
    maturity: date
    type: str


@dataclass(kw_only=True)
class RealEstateCFEntry(BaseHistoricEntry):
    interest_rate: Dezimal
    maturity: date
    extended_maturity: Optional[date]
    type: str
    business_type: str


@dataclass
class Historic:
    entries: list[BaseHistoricEntry]


@dataclass
class HistoricQueryRequest:
    entities: Optional[list[UUID]] = None
    excluded_entities: Optional[list[UUID]] = None
    product_types: Optional[list[ProductType]] = None
    page: int = 1
    limit: int = 20
    sort_by: HistoricSortBy = HistoricSortBy.MATURITY
    sort_order: SortOrder = SortOrder.DESC


@dataclass
class SettleManualInvestmentRequest:
    entity_id: UUID
    entry_id: UUID
    product_type: ProductType
    maturity: Optional[datetime] = None
    interests: Optional[Dezimal] = None
    fees: Dezimal = Dezimal(0)
    retentions: Dezimal = Dezimal(0)
    pending_capital: Dezimal = Dezimal(0)
    create_investment_tx: bool = False


@dataclass
class PartialAmortizeManualInvestmentRequest:
    entity_id: UUID
    entry_id: UUID
    product_type: ProductType
    amount: Dezimal
    date: Optional[datetime] = None
    interests: Dezimal = Dezimal(0)
    fees: Dezimal = Dezimal(0)
    retentions: Dezimal = Dezimal(0)
    create_investment_tx: bool = False


@dataclass
class UnsettleManualInvestmentRequest:
    entry_id: UUID


class HistoricTxDeletion(str, Enum):
    NONE = "NONE"
    SETTLEMENT = "SETTLEMENT"
    ALL = "ALL"


@dataclass
class DeleteManualHistoricEntryRequest:
    entry_id: UUID
    tx_deletion: HistoricTxDeletion = HistoricTxDeletion.NONE
