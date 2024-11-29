from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from domain.bank import Bank


class TxType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"

    INVESTMENT = "INVESTMENT"
    MATURITY = "MATURITY"


class TxProductType(str, Enum):
    FUND = "FUND"
    STOCK_ETF = "STOCK_ETF"
    SEGO = "SEGO"


@dataclass
class BaseTx:
    id: str
    name: str
    amount: float
    currency: str
    currencySymbol: str
    type: TxType
    date: datetime
    source: Bank


@dataclass
class BaseInvestmentTx(BaseTx):
    productType: TxProductType


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
class SegoTx(BaseInvestmentTx):
    fees: float
    retentions: float
    interests: float


@dataclass
class Transactions:
    investment: list[BaseInvestmentTx]
