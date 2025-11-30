from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from domain.base import BaseData
from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.fetch_record import DataSource
from domain.global_position import EquityType, FundType, ProductType
from pydantic.dataclasses import dataclass


class TxType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    RIGHT_ISSUE = "RIGHT_ISSUE"
    RIGHT_SELL = "RIGHT_SELL"
    SUBSCRIPTION = "SUBSCRIPTION"
    SWAP_FROM = "SWAP_FROM"
    SWAP_TO = "SWAP_TO"

    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    SWITCH_FROM = "SWITCH_FROM"
    SWITCH_TO = "SWITCH_TO"

    INVESTMENT = "INVESTMENT"
    REPAYMENT = "REPAYMENT"
    INTEREST = "INTEREST"

    FEE = "FEE"


@dataclass
class BaseTx(BaseData):
    id: Optional[UUID]
    ref: str
    name: str
    amount: Dezimal
    currency: str
    type: TxType
    date: datetime
    entity: Entity
    source: DataSource
    product_type: ProductType


@dataclass
class BaseInvestmentTx(BaseTx):
    pass


@dataclass
class AccountTx(BaseTx):
    fees: Dezimal
    retentions: Dezimal
    interest_rate: Optional[Dezimal] = None
    avg_balance: Optional[Dezimal] = None
    net_amount: Optional[Dezimal] = None


@dataclass
class StockTx(BaseInvestmentTx):
    shares: Dezimal
    price: Dezimal
    fees: Dezimal
    net_amount: Optional[Dezimal] = None
    isin: Optional[str] = None
    ticker: Optional[str] = None
    market: Optional[str] = None
    retentions: Optional[Dezimal] = None
    order_date: Optional[datetime] = None
    linked_tx: Optional[str] = None
    equity_type: Optional[EquityType] = None


@dataclass
class CryptoCurrencyTx(BaseInvestmentTx):
    currency_amount: Dezimal
    symbol: str
    price: Dezimal
    fees: Dezimal
    contract_address: Optional[str] = None
    net_amount: Optional[Dezimal] = None
    retentions: Optional[Dezimal] = None
    order_date: Optional[datetime] = None


@dataclass
class FundTx(BaseInvestmentTx):
    shares: Dezimal
    price: Dezimal
    fees: Dezimal
    net_amount: Optional[Dezimal] = None
    isin: Optional[str] = None
    market: Optional[str] = None
    retentions: Optional[Dezimal] = None
    order_date: Optional[datetime] = None
    fund_type: Optional[FundType] = None


@dataclass
class FundPortfolioTx(BaseInvestmentTx):
    portfolio_name: str
    iban: Optional[str] = None
    fees: Dezimal = Dezimal(0)


@dataclass
class FactoringTx(BaseInvestmentTx):
    fees: Dezimal
    retentions: Dezimal
    net_amount: Optional[Dezimal] = None


@dataclass
class RealEstateCFTx(BaseInvestmentTx):
    fees: Dezimal
    retentions: Dezimal
    net_amount: Optional[Dezimal] = None


@dataclass
class DepositTx(BaseInvestmentTx):
    fees: Dezimal
    retentions: Dezimal
    net_amount: Optional[Dezimal] = None


@dataclass
class Transactions:
    investment: Optional[list[BaseInvestmentTx]] = None
    account: Optional[list[AccountTx]] = None

    def __add__(self, other):
        investment = (self.investment or []) + (other.investment or [])
        account = (self.account or []) + (other.account or [])
        return Transactions(investment=investment, account=account)


@dataclass
class TransactionsResult:
    transactions: list[BaseTx]


@dataclass
class TransactionQueryRequest:
    page: int = 1
    limit: int = 10
    entities: Optional[list[UUID]] = None
    excluded_entities: Optional[list[UUID]] = None
    product_types: Optional[list[ProductType]] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    types: Optional[list[TxType]] = None
    historic_entry_id: Optional[UUID] = None
