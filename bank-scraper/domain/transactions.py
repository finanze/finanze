from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from domain.financial_entity import Entity
from domain.global_position import SourceType


class TxType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    RIGHT_ISSUE = "RIGHT_ISSUE"
    RIGHT_SELL = "RIGHT_SELL"
    SUBSCRIPTION = "SUBSCRIPTION"
    SWAP_FROM = "SWAP_FROM"
    SWAP_TO = "SWAP_TO"

    INVESTMENT = "INVESTMENT"
    MATURITY = "MATURITY"

    INTEREST = "INTEREST"


class TxProductType(str, Enum):
    FUND = "FUND"
    STOCK_ETF = "STOCK_ETF"
    FACTORING = "FACTORING"
    REAL_STATE_CF = "REAL_STATE_CF"


@dataclass
class BaseTx:
    id: str
    name: str
    amount: float
    currency: str
    currencySymbol: str
    type: TxType
    date: datetime
    entity: Entity
    sourceType: SourceType


@dataclass
class BaseInvestmentTx(BaseTx):
    productType: TxProductType


@dataclass
class AccountTx(BaseTx):
    fees: float
    retentions: float
    interestRate: float
    avgBalance: float


@dataclass
class StockTx(BaseInvestmentTx):
    netAmount: float
    isin: str
    ticker: Optional[str]
    shares: float
    price: float
    market: Optional[str]
    fees: float
    retentions: Optional[float]
    orderDate: Optional[datetime]
    linkedTx: Optional[str] = None


@dataclass
class FundTx(BaseInvestmentTx):
    netAmount: float
    isin: str
    shares: float
    price: float
    market: str
    fees: float
    retentions: Optional[float]
    orderDate: datetime


@dataclass
class FactoringTx(BaseInvestmentTx):
    fees: float
    retentions: float
    interests: float


@dataclass
class RealStateCFTx(BaseInvestmentTx):
    fees: float
    retentions: float
    interests: float


@dataclass
class Transactions:
    investment: list[BaseInvestmentTx]
    account: Optional[list[AccountTx]] = None
