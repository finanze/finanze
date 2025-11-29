from dataclasses import field
from datetime import date, datetime
from enum import Enum
from typing import List, Optional, Union
from uuid import UUID

from dateutil.tz import tzlocal
from domain.base import BaseData
from domain.commodity import CommodityRegister
from domain.crypto import CryptoAsset
from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.exception.exceptions import MissingFieldsError
from domain.fetch_record import DataSource
from domain.profitability import annualized_profitability
from pydantic.dataclasses import dataclass


@dataclass
class ManualEntryData:
    tracker_key: Optional[str] = None


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
    BOND = "BOND"
    DERIVATIVE = "DERIVATIVE"


class AccountType(str, Enum):
    CHECKING = "CHECKING"
    VIRTUAL_WALLET = "VIRTUAL_WALLET"
    BROKERAGE = "BROKERAGE"
    SAVINGS = "SAVINGS"
    FUND_PORTFOLIO = "FUND_PORTFOLIO"


@dataclass
class Account(BaseData):
    id: Optional[UUID]
    total: Dezimal
    currency: str
    type: AccountType
    name: Optional[str] = None
    iban: Optional[str] = None
    interest: Optional[Dezimal] = None
    retained: Optional[Dezimal] = None
    pending_transfers: Optional[Dezimal] = None
    source: DataSource = DataSource.REAL


class CardType(str, Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


@dataclass
class Card(BaseData):
    id: Optional[UUID]
    currency: str
    type: CardType
    used: Dezimal
    active: bool = True
    limit: Optional[Dezimal] = None
    name: Optional[str] = None
    ending: Optional[str | int] = None
    related_account: Optional[UUID] = None
    source: DataSource = DataSource.REAL


class LoanType(str, Enum):
    MORTGAGE = "MORTGAGE"
    STANDARD = "STANDARD"


class InterestType(str, Enum):
    FIXED = "FIXED"
    VARIABLE = "VARIABLE"
    MIXED = "MIXED"


@dataclass
class Loan(BaseData):
    id: Optional[UUID]
    type: LoanType
    currency: str
    current_installment: Dezimal
    interest_rate: Dezimal
    loan_amount: Dezimal
    creation: date
    maturity: date
    principal_outstanding: Dezimal
    principal_paid: Optional[Dezimal] = None
    interest_type: InterestType = InterestType.FIXED
    next_payment_date: Optional[date] = None
    euribor_rate: Optional[Dezimal] = None
    fixed_years: Optional[int] = None
    name: Optional[str] = None
    unpaid: Optional[Dezimal] = None
    source: DataSource = DataSource.REAL

    def __post_init__(self):
        self.principal_paid = self.loan_amount - self.principal_outstanding


class AssetType(str, Enum):
    EQUITY = "EQUITY"
    FIXED_INCOME = "FIXED_INCOME"
    MONEY_MARKET = "MONEY_MARKET"
    MIXED = "MIXED"
    OTHER = "OTHER"


class FundType(str, Enum):
    MUTUAL_FUND = "MUTUAL_FUND"
    PRIVATE_EQUITY = "PRIVATE_EQUITY"
    PENSION_FUND = "PENSION_FUND"


class EquityType(str, Enum):
    STOCK = "STOCK"
    ETF = "ETF"


@dataclass
class StockDetail(BaseData):
    id: Optional[UUID]
    name: str
    ticker: str
    isin: str
    shares: Dezimal
    market_value: Dezimal
    currency: str
    type: EquityType
    initial_investment: Optional[Dezimal] = None
    average_buy_price: Optional[Dezimal] = None
    market: str = ""
    subtype: Optional[str] = None
    info_sheet_url: Optional[str] = None
    manual_data: Optional[ManualEntryData] = None
    source: DataSource = DataSource.REAL

    def __post_init__(self):
        ii = self.initial_investment
        abp = self.average_buy_price
        shares = self.shares

        if ii is None and abp is not None and shares and shares != 0:
            self.initial_investment = abp * shares
        elif abp is None and ii is not None and shares and shares != 0:
            self.average_buy_price = ii / shares
        elif ii is None and abp is None:
            raise MissingFieldsError(["initial_investment", "average_buy_price"])


@dataclass
class FundPortfolio(BaseData):
    id: Optional[UUID]
    name: Optional[str] = None
    currency: Optional[str] = None
    initial_investment: Optional[Dezimal] = None
    market_value: Optional[Dezimal] = None
    account_id: Optional[UUID] = None
    account: Optional[Account] = None
    source: DataSource = DataSource.REAL


@dataclass
class FundDetail(BaseData):
    id: Optional[UUID]
    name: str
    isin: str
    market: Optional[str]
    shares: Dezimal
    market_value: Dezimal
    currency: str
    type: FundType
    initial_investment: Optional[Dezimal] = None
    average_buy_price: Optional[Dezimal] = None
    asset_type: Optional[AssetType] = None
    portfolio: Optional[FundPortfolio] = None
    info_sheet_url: Optional[str] = None
    manual_data: Optional[ManualEntryData] = None
    source: DataSource = DataSource.REAL

    def __post_init__(self):
        ii = self.initial_investment
        abp = self.average_buy_price
        shares = self.shares

        if ii is None and abp is not None and shares and shares != 0:
            self.initial_investment = abp * shares
        elif abp is None and ii is not None and shares and shares != 0:
            self.average_buy_price = ii / shares
        elif ii is None and abp is None:
            raise MissingFieldsError(["initial_investment", "average_buy_price"])


@dataclass
class FactoringDetail(BaseData):
    id: Optional[UUID]
    name: str
    amount: Dezimal
    currency: str
    interest_rate: Dezimal
    start: datetime
    maturity: date
    type: str
    state: str
    last_invest_date: Optional[datetime] = None
    profitability: Optional[Dezimal] = None
    late_interest_rate: Optional[Dezimal] = None
    gross_interest_rate: Optional[Dezimal] = None
    gross_late_interest_rate: Optional[Dezimal] = None
    source: DataSource = DataSource.REAL

    def __post_init__(self):
        if self.gross_interest_rate is None:
            self.gross_interest_rate = self.interest_rate
        if (
            self.gross_late_interest_rate is None
            and self.late_interest_rate is not None
        ):
            self.gross_late_interest_rate = self.late_interest_rate
        if self.last_invest_date is None:
            self.last_invest_date = self.start
        if self.profitability is None:
            self.profitability = annualized_profitability(
                interest_rate=self.interest_rate,
                start_dt=self.start,
                maturity=self.maturity,
                late_interest_rate=self.late_interest_rate,
            )


@dataclass
class RealEstateCFDetail(BaseData):
    id: Optional[UUID]
    name: str
    amount: Dezimal
    pending_amount: Dezimal
    currency: str
    interest_rate: Dezimal
    start: datetime
    maturity: date
    type: str
    state: str
    business_type: str = ""
    last_invest_date: Optional[datetime] = None
    profitability: Optional[Dezimal] = None
    extended_maturity: Optional[date] = None
    extended_interest_rate: Optional[Dezimal] = None
    source: DataSource = DataSource.REAL

    def __post_init__(self):
        if not self.last_invest_date:
            self.last_invest_date = self.start
        if self.profitability is None:
            self.profitability = annualized_profitability(
                interest_rate=self.interest_rate,
                start_dt=self.start,
                maturity=self.maturity,
                extended_maturity=self.extended_maturity,
                extended_interest_rate=self.extended_interest_rate,
            )


@dataclass
class Deposit(BaseData):
    id: Optional[UUID]
    name: str
    amount: Dezimal
    currency: str
    interest_rate: Dezimal
    creation: datetime
    maturity: date
    expected_interests: Optional[Dezimal] = None
    source: DataSource = DataSource.REAL

    def __post_init__(self):
        if self.expected_interests is None and self.amount is not None:
            prof = annualized_profitability(
                interest_rate=self.interest_rate,
                start_dt=self.creation,
                maturity=self.maturity,
            )
            self.expected_interests = round(self.amount * prof, 2)


class CryptoCurrencyType(str, Enum):
    NATIVE = "NATIVE"
    TOKEN = "TOKEN"


@dataclass
class CryptoCurrencyPosition(BaseData):
    id: UUID
    symbol: str
    amount: Dezimal
    type: CryptoCurrencyType
    name: Optional[str] = None
    crypto_asset: Optional[CryptoAsset] = None
    market_value: Optional[Dezimal] = None
    currency: Optional[str] = None
    contract_address: Optional[str] = None
    initial_investment: Optional[Dezimal] = None
    average_buy_price: Optional[Dezimal] = None
    investment_currency: Optional[str] = None
    wallet_address: Optional[str] = None
    wallet_name: Optional[str] = None


@dataclass
class CryptoCurrencyWallet(BaseData):
    id: UUID
    address: Optional[str] = None
    name: Optional[str] = None
    assets: list[CryptoCurrencyPosition] = field(default_factory=list)


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
    source: DataSource = DataSource.REAL

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
    products: Optional[list[ProductType]] = None


@dataclass
class UpdatePositionRequest:
    products: ProductPositions
    entity_id: Optional[UUID] = None
    new_entity_name: Optional[str] = None


@dataclass
class ManualPositionData:
    entry_id: UUID
    global_position_id: UUID
    product_type: ProductType
    data: ManualEntryData
