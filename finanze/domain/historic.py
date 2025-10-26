from datetime import date, datetime
from typing import Optional
from uuid import UUID

from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.global_position import ProductType
from domain.transactions import BaseInvestmentTx
from pydantic.dataclasses import dataclass


@dataclass
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


@dataclass
class FactoringEntry(BaseHistoricEntry):
    interest_rate: Dezimal
    gross_interest_rate: Dezimal
    maturity: date
    type: str


@dataclass
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
