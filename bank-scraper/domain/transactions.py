from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic.dataclasses import dataclass

from domain.global_position import SourceType
from domain.base import BaseData


class ProductType(str, Enum):
    FUND = "FUND"
    STOCK_ETF = "STOCK_ETF"
    FACTORING = "FACTORING"
    REAL_STATE_CF = "REAL_STATE_CF"


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


@dataclass
class BaseTx(BaseData):
    id: str
    name: str
    amount: float
    currency: str
    currencySymbol: str
    type: TxType
    date: datetime
    entity: str
    sourceType: SourceType


@dataclass
class BaseInvestmentTx(BaseTx):
    productType: ProductType


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
    shares: float
    price: float
    fees: float
    ticker: Optional[str] = None
    market: Optional[str] = None
    retentions: Optional[float] = None
    orderDate: Optional[datetime] = None
    linkedTx: Optional[str] = None


@dataclass
class FundTx(BaseInvestmentTx):
    netAmount: float
    isin: str
    shares: float
    price: float
    market: str
    fees: float
    retentions: Optional[float] = None
    orderDate: Optional[datetime] = None


@dataclass
class FactoringTx(BaseInvestmentTx):
    netAmount: float
    fees: float
    retentions: float
    interests: float


@dataclass
class RealStateCFTx(BaseInvestmentTx):
    netAmount: float
    fees: float
    retentions: float
    interests: float


@dataclass
class Transactions:
    investment: Optional[list[BaseInvestmentTx]] = None
    account: Optional[list[AccountTx]] = None

    def __add__(self, other):
        investment = (self.investment or []) + (other.investment or [])
        account = (self.account or []) + (other.account or [])
        return Transactions(investment=investment, account=account)
