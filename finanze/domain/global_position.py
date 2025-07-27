from dataclasses import field
from datetime import date, datetime
from enum import Enum
from typing import List, Optional, Union
from uuid import UUID

from dateutil.tz import tzlocal
from domain.base import BaseData
from domain.commodity import CommodityRegister
from domain.dezimal import Dezimal
from domain.entity import Entity
from pydantic.dataclasses import dataclass


class ProductType(str, Enum):
    ACCOUNT = "ACCOUNT"
    CARD = "CARD"
    LOAN = "LOAN"
    STOCK_ETF = "STOCK_ETF"
    FUND = "FUND"
    FUND_PORTFOLIO = "FUND_PORTFOLIO"
    DEPOSIT = "DEPOSIT"
    FACTORING = "FACTORING"
    REAL_ESTATE_CF = "REAL_ESTATE_CF"
    CROWDLENDING = "CROWDLENDING"
    CRYPTO = "CRYPTO"
    COMMODITY = "COMMODITY"


class AccountType(str, Enum):
    CHECKING = "CHECKING"
    VIRTUAL_WALLET = "VIRTUAL_WALLET"
    BROKERAGE = "BROKERAGE"
    SAVINGS = "SAVINGS"
    FUND_PORTFOLIO = "FUND_PORTFOLIO"


@dataclass
class Account(BaseData):
    id: UUID
    total: Dezimal
    currency: str
    type: AccountType
    name: Optional[str] = None
    iban: Optional[str] = None
    interest: Optional[Dezimal] = None
    retained: Optional[Dezimal] = None
    pending_transfers: Optional[Dezimal] = None


class CardType(str, Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


@dataclass
class Card(BaseData):
    id: UUID
    currency: str
    type: CardType
    used: Dezimal
    active: bool
    limit: Optional[Dezimal] = None
    name: Optional[str] = None
    ending: Optional[str | int] = None
    related_account: Optional[UUID] = None


class LoanType(str, Enum):
    MORTGAGE = "MORTGAGE"
    STANDARD = "STANDARD"


@dataclass
class Loan(BaseData):
    id: UUID
    type: LoanType
    currency: str
    current_installment: Dezimal
    interest_rate: Dezimal
    loan_amount: Dezimal
    next_payment_date: date
    principal_outstanding: Dezimal
    principal_paid: Dezimal
    name: Optional[str] = None
    creation: Optional[date] = None
    maturity: Optional[date] = None
    unpaid: Optional[Dezimal] = None


@dataclass
class StockDetail(BaseData):
    id: UUID
    name: str
    ticker: str
    isin: str
    market: str
    shares: Dezimal
    initial_investment: Dezimal
    average_buy_price: Dezimal
    market_value: Dezimal
    currency: str
    type: str
    subtype: Optional[str] = None


@dataclass
class FundPortfolio(BaseData):
    id: UUID
    name: Optional[str] = None
    currency: Optional[str] = None
    initial_investment: Optional[Dezimal] = None
    market_value: Optional[Dezimal] = None


@dataclass
class FundDetail(BaseData):
    id: UUID
    name: str
    isin: str
    market: str
    shares: Dezimal
    initial_investment: Dezimal
    average_buy_price: Dezimal
    market_value: Dezimal
    currency: str
    portfolio: Optional[FundPortfolio] = None


@dataclass
class FactoringDetail(BaseData):
    id: UUID
    name: str
    amount: Dezimal
    currency: str
    interest_rate: Dezimal
    gross_interest_rate: Dezimal
    last_invest_date: datetime
    maturity: date
    type: str
    state: str


@dataclass
class RealEstateCFDetail(BaseData):
    id: UUID
    name: str
    amount: Dezimal
    pending_amount: Dezimal
    currency: str
    interest_rate: Dezimal
    last_invest_date: datetime
    maturity: date
    type: str
    business_type: str
    state: str
    extended_maturity: Optional[date] = None


@dataclass
class Deposit(BaseData):
    id: UUID
    name: str
    amount: Dezimal
    currency: str
    expected_interests: Dezimal
    interest_rate: Dezimal
    creation: datetime
    maturity: date


class CryptoCurrency(str, Enum):
    BITCOIN = "BITCOIN"
    ETHEREUM = "ETHEREUM"
    LITECOIN = "LITECOIN"
    TRON = "TRON"
    BNB = "BNB"


class CryptoToken(str, Enum):
    USDT = "USDT"
    USDC = "USDC"


CryptoAsset = CryptoCurrency | CryptoToken

CRYPTO_SYMBOLS = {
    CryptoCurrency.BITCOIN: "BTC",
    CryptoCurrency.ETHEREUM: "ETH",
    CryptoCurrency.LITECOIN: "LTC",
    CryptoCurrency.TRON: "TRX",
    CryptoCurrency.BNB: "BNB",
    CryptoToken.USDT: "USDT",
    CryptoToken.USDC: "USDC",
}


@dataclass
class CryptoCurrencyToken(BaseData):
    id: UUID
    token_id: str
    name: str
    symbol: str
    token: CryptoToken
    amount: Dezimal
    initial_investment: Optional[Dezimal] = None
    average_buy_price: Optional[Dezimal] = None
    investment_currency: Optional[str] = None
    market_value: Optional[Dezimal] = None
    currency: Optional[str] = None
    type: Optional[str] = None


@dataclass
class CryptoCurrencyWallet(BaseData):
    id: UUID
    wallet_connection_id: Optional[UUID]
    symbol: str
    crypto: CryptoCurrency
    amount: Dezimal
    address: Optional[str] = None
    name: Optional[str] = None
    initial_investment: Optional[Dezimal] = None
    average_buy_price: Optional[Dezimal] = None
    investment_currency: Optional[str] = None
    market_value: Optional[Dezimal] = None
    currency: Optional[str] = None
    tokens: list[CryptoCurrencyToken] = None


class CryptoInitialInvestmentType(str, Enum):
    CRYPTO = "CRYPTO"
    TOKEN = "TOKEN"


@dataclass
class CryptoInitialInvestment(BaseData):
    wallet_connection_id: UUID
    symbol: str
    type: CryptoInitialInvestmentType
    initial_investment: Optional[Dezimal]
    average_buy_price: Optional[Dezimal]
    investment_currency: str
    currency: str


@dataclass
class Commodity(BaseData, CommodityRegister):
    id: UUID = field(default_factory=UUID)


@dataclass
class Crowdlending(BaseData):
    id: UUID
    total: Optional[Dezimal]
    weighted_interest_rate: Optional[Dezimal]
    currency: str
    distribution: Optional[dict] = None
    entries: Optional[list] = None


@dataclass
class Accounts:
    entries: List[Account]


@dataclass
class Cards:
    entries: List[Card]


@dataclass
class Loans:
    entries: List[Loan]


@dataclass
class StockInvestments:
    entries: List[StockDetail]


@dataclass
class FundInvestments:
    entries: List[FundDetail]


@dataclass
class FundPortfolios:
    entries: List[FundPortfolio]


@dataclass
class FactoringInvestments:
    entries: List[FactoringDetail]


@dataclass
class RealEstateCFInvestments:
    entries: List[RealEstateCFDetail]


@dataclass
class Deposits:
    entries: List[Deposit]


@dataclass
class CryptoCurrencies:
    entries: List[CryptoCurrencyWallet]


@dataclass
class Commodities:
    entries: List[Commodity]


ProductPosition = Union[
    Accounts,
    Cards,
    Loans,
    StockInvestments,
    FundInvestments,
    FundPortfolios,
    FactoringInvestments,
    RealEstateCFInvestments,
    Deposits,
    Crowdlending,
    CryptoCurrencies,
    Commodities,
]


ProductPositions = dict[ProductType, ProductPosition]


@dataclass
class GlobalPosition:
    id: UUID
    entity: Entity
    date: Optional[datetime] = None
    products: ProductPositions = field(default_factory=dict)
    is_real: bool = True

    def __post_init__(self):
        if self.date is None:
            self.date = datetime.now(tzlocal())


@dataclass
class HistoricalPosition:
    positions: ProductPositions


@dataclass
class EntitiesPosition:
    positions: dict[str, GlobalPosition]


@dataclass
class PositionQueryRequest:
    entities: Optional[list[UUID]] = None
    excluded_entities: Optional[list[UUID]] = None
    real: Optional[bool] = None
