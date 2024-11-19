from dataclasses import dataclass
from datetime import datetime, date
from typing import List, Optional


@dataclass
class AccountAdditionalData:
    averageInterestRate: Optional[float]
    remunerationType: Optional[str]


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
class SegoDetail:
    name: str
    amount: float
    interestRate: float
    maturity: str
    type: str


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
class SegoInvestments:
    invested: float
    wallet: float
    weightedInterestRate: float
    details: List[SegoDetail]


@dataclass
class Investments:
    stocks: Optional[StockInvestments] = None
    funds: Optional[FundInvestments] = None
    sego: Optional[SegoInvestments] = None


@dataclass
class BankAdditionalData:
    maintenance: Optional[bool] = None


@dataclass
class BankData:
    account: Account
    lastUpdate: datetime
    cards: Optional[Cards] = None
    mortgage: Optional[Mortgage] = None
    investments: Optional[Investments] = None
    additionalData: Optional[BankAdditionalData] = None
