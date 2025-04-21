from dataclasses import field
from datetime import datetime, date
from enum import Enum
from typing import List, Optional
from uuid import UUID

from dateutil.tz import tzlocal
from pydantic.dataclasses import dataclass

from domain.base import BaseData
from domain.dezimal import Dezimal
from domain.financial_entity import FinancialEntity


class AccountType(str, Enum):
    CHECKING = 'CHECKING'
    VIRTUAL_WALLET = 'VIRTUAL_WALLET'
    BROKERAGE = 'BROKERAGE'
    SAVINGS = 'SAVINGS'


@dataclass
class Account:
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
    CREDIT = 'CREDIT'
    DEBIT = 'DEBIT'


@dataclass
class Card:
    id: UUID
    currency: str
    type: CardType
    used: Dezimal
    active: bool
    limit: Optional[Dezimal] = None
    name: Optional[str] = None
    ending: Optional[str] = None
    related_account: Optional[UUID] = None


class LoanType(str, Enum):
    MORTGAGE = 'MORTGAGE'
    STANDARD = 'STANDARD'


@dataclass
class Loan:
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
class RealStateCFDetail(BaseData):
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
class StockInvestments:
    investment: Optional[Dezimal]
    market_value: Optional[Dezimal]
    details: List[StockDetail]


@dataclass
class FundInvestments:
    investment: Optional[Dezimal]
    market_value: Optional[Dezimal]
    details: List[FundDetail]


@dataclass
class FactoringInvestments:
    total: Optional[Dezimal]
    weighted_interest_rate: Optional[Dezimal]
    details: List[FactoringDetail]


@dataclass
class RealStateCFInvestments:
    total: Optional[Dezimal]
    weighted_interest_rate: Optional[Dezimal]
    details: List[RealStateCFDetail]


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


@dataclass
class Deposits:
    total: Optional[Dezimal]
    expected_interests: Optional[Dezimal]
    weighted_interest_rate: Optional[Dezimal]
    details: List[Deposit]


@dataclass
class Crowdlending:
    id: UUID
    total: Optional[Dezimal]
    weighted_interest_rate: Optional[Dezimal]
    currency: str
    distribution: dict
    details: List


@dataclass
class Investments:
    stocks: Optional[StockInvestments] = None
    funds: Optional[FundInvestments] = None
    factoring: Optional[FactoringInvestments] = None
    real_state_cf: Optional[RealStateCFInvestments] = None
    deposits: Optional[Deposits] = None
    crowdlending: Optional[Crowdlending] = None


@dataclass
class GlobalPosition:
    id: UUID
    entity: FinancialEntity
    date: Optional[datetime] = None
    accounts: list[Account] = field(default_factory=list)
    cards: list[Card] = field(default_factory=list)
    loans: list[Loan] = field(default_factory=list)
    investments: Optional[Investments] = None
    is_real: bool = True

    def __post_init__(self):
        if self.date is None:
            self.date = datetime.now(tzlocal())


@dataclass
class HistoricalPosition:
    investments: Investments
