from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from domain.base import BaseData
from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.fetch_record import DataSource
from domain.global_position import (
    EquityType,
    FundType,
    ProductType,
)
from pydantic.dataclasses import dataclass


class TxType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    RIGHT_ISSUE = "RIGHT_ISSUE"
    RIGHT_SELL = "RIGHT_SELL"
    SUBSCRIPTION = "SUBSCRIPTION"  # Right exercise
    SPLIT = "SPLIT"
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

    INFLOW = "INFLOW"
    OUTFLOW = "OUTFLOW"


ACCOUNT_MOVEMENT_TYPES = {TxType.INFLOW, TxType.OUTFLOW}
ACCOUNT_INCOMING_TYPES = {TxType.INFLOW, TxType.INTEREST}
ACCOUNT_OUTGOING_TYPES = {TxType.OUTFLOW, TxType.FEE}
ACCOUNT_MOVEMENTS_MAX_LOOKBACK_DAYS = 730
MAX_IBAN_LENGTH = 34


def normalize_iban(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return "".join(str(value).split()).upper() or None


def is_valid_iban_format(value: str) -> bool:
    return value.isascii() and value.isalnum() and len(value) <= MAX_IBAN_LENGTH


class LabelOrigin(str, Enum):
    MANUAL = "MANUAL"
    RULE = "RULE"
    EXTERNAL = "EXTERNAL"


@dataclass
class TxLabel:
    label_id: UUID
    origin: LabelOrigin
    rule_id: Optional[UUID] = None
    provider: Optional[str] = None
    confidence: Optional[Dezimal] = None


@dataclass
class TransferPair:
    tx_id: UUID
    entity_id: Optional[UUID] = None
    rule_id: Optional[UUID] = None


@dataclass(kw_only=True)
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
    entity_account_id: Optional[UUID] = None


@dataclass(kw_only=True)
class BaseInvestmentTx(BaseTx):
    pass


@dataclass(kw_only=True)
class AccountTx(BaseTx):
    fees: Dezimal
    retentions: Dezimal
    interest_rate: Optional[Dezimal] = None
    avg_balance: Optional[Dezimal] = None
    net_amount: Optional[Dezimal] = None
    counterparty: Optional[str] = None
    iban: Optional[str] = None
    # ref of the investment tx (same entity) this movement is the cash leg of
    linked_tx: Optional[str] = None
    labels: Optional[list[TxLabel]] = None
    labels_locked: bool = False
    transfer_pair: Optional[TransferPair] = None


@dataclass(kw_only=True)
class StockTx(BaseInvestmentTx):
    shares: Optional[Dezimal] = None
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
    split_ratio: Optional[Dezimal] = None


@dataclass(kw_only=True)
class CryptoCurrencyTx(BaseInvestmentTx):
    currency_amount: Dezimal
    symbol: str
    price: Dezimal
    fees: Dezimal
    contract_address: Optional[str] = None
    net_amount: Optional[Dezimal] = None
    retentions: Optional[Dezimal] = None
    order_date: Optional[datetime] = None


@dataclass(kw_only=True)
class MarketForecastTx(BaseInvestmentTx):
    symbol: str
    size: Dezimal
    price: Dezimal
    fees: Dezimal
    contract_address: Optional[str] = None
    net_amount: Optional[Dezimal] = None
    retentions: Optional[Dezimal] = None
    order_date: Optional[datetime] = None


@dataclass(kw_only=True)
class FundTx(BaseInvestmentTx):
    shares: Optional[Dezimal] = None
    price: Dezimal
    fees: Dezimal
    net_amount: Optional[Dezimal] = None
    isin: Optional[str] = None
    market: Optional[str] = None
    retentions: Optional[Dezimal] = None
    order_date: Optional[datetime] = None
    fund_type: Optional[FundType] = None
    split_ratio: Optional[Dezimal] = None


@dataclass(kw_only=True)
class FundPortfolioTx(BaseInvestmentTx):
    portfolio_name: str
    iban: Optional[str] = None
    fees: Dezimal = Dezimal(0)


@dataclass(kw_only=True)
class FactoringTx(BaseInvestmentTx):
    fees: Dezimal
    retentions: Dezimal
    net_amount: Optional[Dezimal] = None


@dataclass(kw_only=True)
class RealEstateCFTx(BaseInvestmentTx):
    fees: Dezimal
    retentions: Dezimal
    net_amount: Optional[Dezimal] = None


@dataclass(kw_only=True)
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
    labels: Optional[list[UUID]] = None
    excluded_labels: Optional[list[UUID]] = None
    unlabeled: bool = False
    search: Optional[str] = None


@dataclass
class AccountTxSelection:
    ids: Optional[list[UUID]] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    entities: Optional[list[UUID]] = None
    types: Optional[list[TxType]] = None
    with_labels: Optional[list[UUID]] = None
    without_labels: Optional[list[UUID]] = None
    unlabeled_only: bool = False
    include_locked: bool = True
    include_linked: bool = True
    exclude_external_unmatched: bool = False
    search: Optional[str] = None


@dataclass
class TxClassification:
    labels: list[TxLabel]
    locked: bool = False
    linked_tx: Optional[str] = None
    transfer_pair: Optional[TransferPair] = None
    external_unmatched_at: Optional[datetime] = None


@dataclass
class AddManualTransactionRequest:
    txs: list[BaseTx]
    historic_entry_id: Optional[UUID] = None
