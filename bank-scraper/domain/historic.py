from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional

from domain.transactions import ProductType


@dataclass
class BaseHistoricEntry:
    name: str
    invested: float
    returned: Optional[float]
    currency: str
    currencySymbol: str
    lastInvestDate: datetime
    lastTxDate: datetime
    effectiveMaturity: Optional[datetime]
    netReturn: Optional[float]
    fees: Optional[float]
    retentions: Optional[float]
    interests: Optional[float]
    state: Optional[str]
    entity: str
    productType: ProductType
    relatedTxs: list[dict]


@dataclass
class FactoringEntry(BaseHistoricEntry):
    interestRate: float
    netInterestRate: float
    maturity: date
    type: str


@dataclass
class RealStateCFEntry(BaseHistoricEntry):
    interestRate: float
    months: int
    potentialExtension: Optional[int]
    type: str
    businessType: str


@dataclass
class Historic:
    entries: list[BaseHistoricEntry]
