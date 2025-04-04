from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic.dataclasses import dataclass

from domain.base import BaseData
from domain.dezimal import Dezimal
from domain.financial_entity import FinancialEntity


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
    id: UUID
    ref: str
    name: str
    amount: Dezimal
    currency: str
    type: TxType
    date: datetime
    entity: FinancialEntity
    is_real: bool


@dataclass
class BaseInvestmentTx(BaseTx):
    product_type: ProductType


@dataclass
class AccountTx(BaseTx):
    fees: Dezimal
    retentions: Dezimal
    interest_rate: Dezimal
    avg_balance: Dezimal


@dataclass
class StockTx(BaseInvestmentTx):
    net_amount: Dezimal
    isin: str
    shares: Dezimal
    price: Dezimal
    fees: Dezimal
    ticker: Optional[str] = None
    market: Optional[str] = None
    retentions: Optional[Dezimal] = None
    order_date: Optional[datetime] = None
    linked_tx: Optional[str] = None


@dataclass
class FundTx(BaseInvestmentTx):
    net_amount: Dezimal
    isin: str
    shares: Dezimal
    price: Dezimal
    market: str
    fees: Dezimal
    retentions: Optional[Dezimal] = None
    order_date: Optional[datetime] = None


@dataclass
class FactoringTx(BaseInvestmentTx):
    net_amount: Dezimal
    fees: Dezimal
    retentions: Dezimal
    interests: Dezimal


@dataclass
class RealStateCFTx(BaseInvestmentTx):
    net_amount: Dezimal
    fees: Dezimal
    retentions: Dezimal
    interests: Dezimal


@dataclass
class Transactions:
    investment: Optional[list[BaseInvestmentTx]] = None
    account: Optional[list[AccountTx]] = None

    def __add__(self, other):
        investment = (self.investment or []) + (other.investment or [])
        account = (self.account or []) + (other.account or [])
        return Transactions(investment=investment, account=account)
