from datetime import datetime, date
from enum import Enum
from typing import List, Optional

from dateutil.tz import tzlocal
from pydantic.dataclasses import dataclass

from domain.base import BaseData


@dataclass
class AccountAdditionalData:
    averageInterestRate: Optional[float] = None
    remunerationType: Optional[str] = None
    pendingTransfers: Optional[float] = None


@dataclass
class Account:
    total: float
    interest: Optional[float] = None
    retained: Optional[float] = None
    additionalData: Optional[AccountAdditionalData] = None


@dataclass
class Card:
    limit: float
    used: float


@dataclass
class Cards:
    credit: Card
    debit: Card


@dataclass
class Mortgage:
    currentInstallment: float
    interestRate: float
    loanAmount: float
    nextPaymentDate: date
    principalOutstanding: float
    principalPaid: float


@dataclass
class StockDetail(BaseData):
    name: str
    ticker: str
    isin: str
    market: str
    shares: float
    initialInvestment: float
    averageBuyPrice: float
    marketValue: float
    currency: str
    currencySymbol: str
    type: str
    subtype: Optional[str] = None


@dataclass
class FundDetail(BaseData):
    name: str
    isin: str
    market: str
    shares: float
    initialInvestment: float
    averageBuyPrice: float
    marketValue: float
    currency: str
    currencySymbol: str
    lastUpdate: Optional[date] = None


@dataclass
class FactoringDetail(BaseData):
    name: str
    amount: float
    currency: str
    currencySymbol: str
    interestRate: float
    netInterestRate: float
    lastInvestDate: Optional[datetime]
    maturity: date
    type: str
    state: str


@dataclass
class RealStateCFDetail(BaseData):
    name: str
    amount: float
    currency: str
    currencySymbol: str
    interestRate: float
    lastInvestDate: datetime
    months: int
    potentialExtension: Optional[int]
    type: str
    businessType: str
    state: Optional[str]


@dataclass
class StockInvestments:
    initialInvestment: float
    marketValue: float
    details: List[StockDetail]


@dataclass
class FundInvestments:
    initialInvestment: float
    marketValue: float
    details: List[FundDetail]


@dataclass
class FactoringInvestments:
    invested: float
    weightedInterestRate: float
    details: List[FactoringDetail]


@dataclass
class RealStateCFInvestments:
    invested: float
    weightedInterestRate: float
    details: List[RealStateCFDetail]


@dataclass
class Deposit(BaseData):
    name: str
    amount: float
    totalInterests: float
    interestRate: float
    creation: datetime
    maturity: date


@dataclass
class Deposits:
    total: float
    totalInterests: float
    weightedInterestRate: float
    details: List[Deposit]


@dataclass
class Crowdlending:
    total: float
    weightedInterestRate: float
    distribution: dict
    details: List


@dataclass
class Investments:
    stocks: Optional[StockInvestments] = None
    funds: Optional[FundInvestments] = None
    factoring: Optional[FactoringInvestments] = None
    realStateCF: Optional[RealStateCFInvestments] = None
    deposits: Optional[Deposits] = None
    crowdlending: Optional[Crowdlending] = None


@dataclass
class PositionAdditionalData:
    maintenance: Optional[bool] = None


@dataclass
class GlobalPosition:
    date: Optional[datetime] = None
    account: Optional[Account] = None
    cards: Optional[Cards] = None
    mortgage: Optional[Mortgage] = None
    investments: Optional[Investments] = None
    additionalData: Optional[PositionAdditionalData] = None

    def __post_init__(self):
        if self.date is None:
            self.date = datetime.now(tzlocal())


@dataclass
class HistoricalPosition:
    investments: Investments


class SourceType(str, Enum):
    REAL = "REAL"
    VIRTUAL = "VIRTUAL"
