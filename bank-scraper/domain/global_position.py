from dataclasses import dataclass
from datetime import datetime, date
from enum import Enum
from typing import List, Optional

from dateutil.tz import tzlocal


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
class StockDetail:
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
class FundDetail:
    name: str
    isin: str
    market: str
    shares: float
    initialInvestment: float
    averageBuyPrice: float
    marketValue: float
    currency: str
    currencySymbol: str
    lastUpdate: date


@dataclass
class FactoringDetail:
    name: str
    amount: float
    interestRate: float
    netInterestRate: float
    lastInvestDate: Optional[datetime]
    maturity: date
    type: str
    state: str


@dataclass
class RealStateCFDetail:
    name: str
    amount: float
    interestRate: float
    lastInvestDate: date
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
    wallet: float
    weightedInterestRate: float
    details: List[FactoringDetail]


@dataclass
class RealStateCFInvestments:
    invested: float
    wallet: float
    weightedInterestRate: float
    details: List[RealStateCFDetail]


@dataclass
class Investments:
    stocks: Optional[StockInvestments] = None
    funds: Optional[FundInvestments] = None
    factoring: Optional[FactoringInvestments] = None
    realStateCF: Optional[RealStateCFInvestments] = None


@dataclass
class Deposit:
    name: str
    amount: float
    totalInterests: float
    interestRate: float
    creation: date
    maturity: date


@dataclass
class Deposits:
    total: float
    totalInterests: float
    weightedInterestRate: float
    details: List[Deposit]


@dataclass
class PositionAdditionalData:
    maintenance: Optional[bool] = None


@dataclass
class GlobalPosition:
    date: datetime = None
    account: Optional[Account] = None
    cards: Optional[Cards] = None
    mortgage: Optional[Mortgage] = None
    deposits: Optional[Deposits] = None
    investments: Optional[Investments] = None
    additionalData: Optional[PositionAdditionalData] = None

    def __post_init__(self):
        if self.date is None:
            self.date = datetime.now(tzlocal())


class SourceType(str, Enum):
    REAL = "REAL"
    VIRTUAL = "VIRTUAL"
