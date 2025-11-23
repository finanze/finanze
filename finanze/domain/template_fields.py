from enum import Enum
from typing import Any, Optional

from domain.auto_contributions import (
    ContributionFrequency,
    ContributionTargetSubtype,
    ContributionTargetType,
)
from domain.dezimal import Dezimal
from domain.entity import Feature
from domain.global_position import (
    AccountType,
    AssetType,
    CardType,
    EquityType,
    FundType,
    InterestType,
    LoanType,
    ProductType,
)
from domain.template_type import TemplateType
from domain.transactions import TxType
from pydantic.dataclasses import dataclass


class TemplateFieldType(str, Enum):
    TEXT = "TEXT"
    CURRENCY = "CURRENCY"
    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    DATE = "DATE"
    DATETIME = "DATETIME"
    BOOLEAN = "BOOLEAN"
    ENUM = "ENUM"


@dataclass
class TemplateField:
    key: str
    field: str
    type: TemplateFieldType
    enum: Optional[type] = None
    required: bool = False
    or_requires: Optional[list["TemplateField"]] = None
    template_type: Optional[TemplateType] = None
    default_value: Optional[Any] = None
    disabled_default: bool = False

    def __hash__(self):
        return hash(self.field)

    def require(self, *or_requires: "TemplateField") -> "TemplateField":
        copy = self._copy()
        copy.required = True
        if or_requires:
            copy.required = False
            copy.or_requires = list(or_requires)
        return copy

    def with_template(self, template_type: TemplateType) -> "TemplateField":
        copy = self._copy()
        copy.template_type = template_type
        return copy

    def default(self, value: Any) -> "TemplateField":
        copy = self._copy()
        copy.default_value = value
        return copy

    def disable_default(self) -> "TemplateField":
        copy = self._copy()
        copy.disabled_default = True
        return copy

    def _copy(self):
        return TemplateField(
            key=self.key,
            field=self.field,
            type=self.type,
            enum=self.enum,
            required=self.required,
            or_requires=self.or_requires,
            template_type=self.template_type,
            default_value=self.default_value,
            disabled_default=self.disabled_default,
        )


ENTITY = TemplateField(
    key="entity", field="entity", type=TemplateFieldType.TEXT
).disable_default()
PRODUCT_TYPE = TemplateField(
    key="product_type",
    field="product_type",
    type=TemplateFieldType.ENUM,
    enum=ProductType,
)

TOTAL = TemplateField(key="total", field="total", type=TemplateFieldType.DECIMAL)
CURRENCY = TemplateField(
    key="currency", field="currency", type=TemplateFieldType.CURRENCY
)
ACCOUNT_TYPE = TemplateField(
    key="type.account",
    field="type",
    type=TemplateFieldType.ENUM,
    enum=AccountType,
)
NAME = TemplateField(key="name", field="name", type=TemplateFieldType.TEXT)
IBAN = TemplateField(key="iban", field="iban", type=TemplateFieldType.TEXT)
INTEREST = TemplateField(
    key="interest", field="interest", type=TemplateFieldType.DECIMAL
)
RETAINED = TemplateField(
    key="retained", field="retained", type=TemplateFieldType.DECIMAL
)
PENDING_TRANSFERS = TemplateField(
    key="pending_transfers",
    field="pending_transfers",
    type=TemplateFieldType.DECIMAL,
)


@dataclass
class FieldGroup:
    feature: Feature
    product: Optional[ProductType]
    fields: list[TemplateField]
    template_type: Optional[TemplateType] = None


ACCOUNT_FIELDS = FieldGroup(
    feature=Feature.POSITION,
    product=ProductType.ACCOUNT,
    fields=[
        NAME,
        IBAN,
        TOTAL.require(),
        CURRENCY.require(),
        ACCOUNT_TYPE.require().default(AccountType.CHECKING),
        INTEREST,
        RETAINED,
        PENDING_TRANSFERS,
        PRODUCT_TYPE.with_template(TemplateType.EXPORT),
        ENTITY,
    ],
)

CARD_TYPE = TemplateField(
    key="type.card",
    field="type",
    type=TemplateFieldType.ENUM,
    enum=CardType,
)
USED = TemplateField(key="used", field="used", type=TemplateFieldType.DECIMAL)
ACTIVE = TemplateField(key="active", field="active", type=TemplateFieldType.BOOLEAN)
LIMIT = TemplateField(key="limit", field="limit", type=TemplateFieldType.DECIMAL)
CARD_ENDING = TemplateField(key="ending", field="ending", type=TemplateFieldType.TEXT)

CARD_FIELDS = FieldGroup(
    feature=Feature.POSITION,
    product=ProductType.CARD,
    fields=[
        NAME,
        CARD_ENDING,
        CURRENCY.require(),
        CARD_TYPE.require(),
        USED.require(),
        LIMIT,
        ACTIVE.default(True),
        PRODUCT_TYPE.with_template(TemplateType.EXPORT),
        ENTITY,
    ],
)

LOAN_TYPE = TemplateField(
    key="type.loan",
    field="type",
    type=TemplateFieldType.ENUM,
    enum=LoanType,
)
CURRENT_INSTALLMENT = TemplateField(
    key="current_installment",
    field="current_installment",
    type=TemplateFieldType.DECIMAL,
)
INTEREST_RATE = TemplateField(
    key="interest_rate",
    field="interest_rate",
    type=TemplateFieldType.DECIMAL,
)
LOAN_AMOUNT = TemplateField(
    key="loan_amount",
    field="loan_amount",
    type=TemplateFieldType.DECIMAL,
)
PRINCIPAL_OUTSTANDING = TemplateField(
    key="principal_outstanding",
    field="principal_outstanding",
    type=TemplateFieldType.DECIMAL,
)
PRINCIPAL_PAID = TemplateField(
    key="principal_paid",
    field="principal_paid",
    type=TemplateFieldType.DECIMAL,
)
INTEREST_TYPE = TemplateField(
    key="interest_type",
    field="interest_type",
    type=TemplateFieldType.ENUM,
    enum=InterestType,
)
CREATION = TemplateField(key="creation", field="creation", type=TemplateFieldType.DATE)
MATURITY = TemplateField(key="maturity", field="maturity", type=TemplateFieldType.DATE)
NEXT_PAYMENT_DATE = TemplateField(
    key="next_payment_date",
    field="next_payment_date",
    type=TemplateFieldType.DATE,
)
EURIBOR_RATE = TemplateField(
    key="euribor_rate",
    field="euribor_rate",
    type=TemplateFieldType.DECIMAL,
)
FIXED_YEARS = TemplateField(
    key="fixed_years",
    field="fixed_years",
    type=TemplateFieldType.INTEGER,
)
UNPAID = TemplateField(key="unpaid", field="unpaid", type=TemplateFieldType.DECIMAL)

LOAN_FIELDS = FieldGroup(
    feature=Feature.POSITION,
    product=ProductType.LOAN,
    fields=[
        NAME,
        LOAN_TYPE.default(LoanType.STANDARD),
        LOAN_AMOUNT.require(),
        CURRENCY.require(),
        CURRENT_INSTALLMENT.require(),
        INTEREST_TYPE.require(),
        INTEREST_RATE.require(),
        CREATION.require(),
        MATURITY.require(),
        PRINCIPAL_OUTSTANDING.require(),
        PRINCIPAL_PAID,
        NEXT_PAYMENT_DATE,
        EURIBOR_RATE,
        FIXED_YEARS,
        UNPAID,
        PRODUCT_TYPE.with_template(TemplateType.EXPORT),
        ENTITY,
    ],
)

TICKER = TemplateField(key="ticker", field="ticker", type=TemplateFieldType.TEXT)
ISIN = TemplateField(key="isin", field="isin", type=TemplateFieldType.TEXT)
MARKET = TemplateField(key="market", field="market", type=TemplateFieldType.TEXT)
SHARES = TemplateField(key="shares", field="shares", type=TemplateFieldType.DECIMAL)
INITIAL_INVESTMENT = TemplateField(
    key="initial_investment",
    field="initial_investment",
    type=TemplateFieldType.DECIMAL,
)
AVERAGE_BUY_PRICE = TemplateField(
    key="average_buy_price",
    field="average_buy_price",
    type=TemplateFieldType.DECIMAL,
)
MARKET_VALUE = TemplateField(
    key="market_value",
    field="market_value",
    type=TemplateFieldType.DECIMAL,
)
EQUITY_TYPE = TemplateField(
    key="type.equity",
    field="type",
    type=TemplateFieldType.ENUM,
    enum=EquityType,
)
SUBTYPE = TemplateField(key="subtype", field="subtype", type=TemplateFieldType.TEXT)
INFO_SHEET_URL = TemplateField(
    key="info_sheet_url",
    field="info_sheet_url",
    type=TemplateFieldType.TEXT,
)

STOCK_ETF_FIELDS = FieldGroup(
    feature=Feature.POSITION,
    product=ProductType.STOCK_ETF,
    fields=[
        NAME.require(),
        TICKER.require(),
        ISIN.require(),
        MARKET,
        SHARES.require(),
        INITIAL_INVESTMENT.require(AVERAGE_BUY_PRICE),
        AVERAGE_BUY_PRICE.require(INITIAL_INVESTMENT),
        MARKET_VALUE.require(),
        CURRENCY.require(),
        EQUITY_TYPE.require().default(EquityType.STOCK),
        SUBTYPE,
        INFO_SHEET_URL,
        PRODUCT_TYPE.with_template(TemplateType.EXPORT),
        ENTITY,
    ],
)

FUND_TYPE = TemplateField(
    key="type.fund",
    field="type",
    type=TemplateFieldType.ENUM,
    enum=FundType,
)
ASSET_TYPE = TemplateField(
    key="asset_type",
    field="asset_type",
    type=TemplateFieldType.ENUM,
    enum=AssetType,
)
PORTFOLIO_NAME = TemplateField(
    key="portfolio", field="portfolio.name", type=TemplateFieldType.TEXT
)

FUND_FIELDS = FieldGroup(
    feature=Feature.POSITION,
    product=ProductType.FUND,
    fields=[
        NAME.require(),
        ISIN.require(),
        MARKET,
        SHARES.require(),
        INITIAL_INVESTMENT.require(AVERAGE_BUY_PRICE),
        AVERAGE_BUY_PRICE.require(INITIAL_INVESTMENT),
        MARKET_VALUE.require(),
        CURRENCY.require(),
        FUND_TYPE.require().default(FundType.MUTUAL_FUND),
        ASSET_TYPE,
        PORTFOLIO_NAME,
        INFO_SHEET_URL,
        PRODUCT_TYPE.with_template(TemplateType.EXPORT),
        ENTITY,
    ],
)

AMOUNT = TemplateField(key="amount", field="amount", type=TemplateFieldType.DECIMAL)
PROFITABILITY = TemplateField(
    key="profitability",
    field="profitability",
    type=TemplateFieldType.DECIMAL,
)
LAST_INVEST_DATE = TemplateField(
    key="last_invest_date",
    field="last_invest_date",
    type=TemplateFieldType.DATETIME,
)
FACTORING_TYPE = TemplateField(
    key="type.factoring", field="type", type=TemplateFieldType.TEXT
)
STATE = TemplateField(key="state", field="state", type=TemplateFieldType.TEXT)

FACTORING_FIELDS = FieldGroup(
    feature=Feature.POSITION,
    product=ProductType.FACTORING,
    fields=[
        NAME.require(),
        AMOUNT.require(),
        CURRENCY.require(),
        INTEREST_RATE.require(),
        PROFITABILITY.with_template(TemplateType.EXPORT),
        LAST_INVEST_DATE.require(),
        MATURITY.require(),
        FACTORING_TYPE.require(),
        STATE.require(),
        PRODUCT_TYPE.with_template(TemplateType.EXPORT),
        ENTITY,
    ],
)

REAL_ESTATE_CF_TYPE = TemplateField(
    key="type.real_estate_cf", field="type", type=TemplateFieldType.TEXT
)
PENDING_AMOUNT = TemplateField(
    key="pending_amount",
    field="pending_amount",
    type=TemplateFieldType.DECIMAL,
)
BUSINESS_TYPE = TemplateField(
    key="business_type",
    field="business_type",
    type=TemplateFieldType.TEXT,
)
EXTENDED_MATURITY = TemplateField(
    key="extended_maturity",
    field="extended_maturity",
    type=TemplateFieldType.DATE,
)

REAL_ESTATE_CF_FIELDS = FieldGroup(
    feature=Feature.POSITION,
    product=ProductType.REAL_ESTATE_CF,
    fields=[
        NAME.require(),
        AMOUNT.require(),
        PENDING_AMOUNT.require(),
        CURRENCY.require(),
        INTEREST_RATE.require(),
        PROFITABILITY.with_template(TemplateType.EXPORT),
        LAST_INVEST_DATE.require(),
        MATURITY.require(),
        REAL_ESTATE_CF_TYPE.require(),
        BUSINESS_TYPE,
        STATE.require(),
        EXTENDED_MATURITY,
        PRODUCT_TYPE.with_template(TemplateType.EXPORT),
        ENTITY,
    ],
)

EXPECTED_INTERESTS = TemplateField(
    key="expected_interests",
    field="expected_interests",
    type=TemplateFieldType.DECIMAL,
)

DEPOSIT_FIELDS = FieldGroup(
    feature=Feature.POSITION,
    product=ProductType.DEPOSIT,
    fields=[
        NAME.require(),
        AMOUNT.require(),
        CURRENCY.require(),
        EXPECTED_INTERESTS.with_template(TemplateType.EXPORT),
        INTEREST_RATE.require(),
        CREATION.require(),
        MATURITY.require(),
        PRODUCT_TYPE.with_template(TemplateType.EXPORT),
        ENTITY,
    ],
)

SYMBOL = TemplateField(
    key="symbol",
    field="symbol",
    type=TemplateFieldType.TEXT,
)
CONTRACT_ADDRESS = TemplateField(
    key="contract_address",
    field="contract_address",
    type=TemplateFieldType.TEXT,
)
WALLET_ADDRESS = TemplateField(
    key="wallet_address",
    field="wallet_address",
    type=TemplateFieldType.TEXT,
)
WALLET_NAME = TemplateField(
    key="wallet_name", field="wallet_name", type=TemplateFieldType.TEXT
)
CRYPTO_FIELDS = FieldGroup(
    feature=Feature.POSITION,
    product=ProductType.CRYPTO,
    template_type=TemplateType.EXPORT,
    fields=[
        SYMBOL,
        AMOUNT,
        NAME,
        MARKET_VALUE,
        CURRENCY,
        CONTRACT_ADDRESS,
        WALLET_ADDRESS,
        WALLET_NAME,
        PRODUCT_TYPE.with_template(TemplateType.EXPORT),
    ],
)

REFERENCE = TemplateField(key="reference", field="ref", type=TemplateFieldType.TEXT)
TX_TYPE = TemplateField(
    key="type.transaction",
    field="type",
    type=TemplateFieldType.ENUM,
    enum=TxType,
)
DATE = TemplateField(key="date", field="date", type=TemplateFieldType.DATETIME)

FEES = TemplateField(key="fees", field="fees", type=TemplateFieldType.DECIMAL)
RETENTIONS = TemplateField(
    key="retentions", field="retentions", type=TemplateFieldType.DECIMAL
)
AVERAGE_BALANCE = TemplateField(
    key="average_balance",
    field="avg_balance",
    type=TemplateFieldType.DECIMAL,
)
NET_AMOUNT = TemplateField(
    key="net_amount", field="net_amount", type=TemplateFieldType.DECIMAL
)

PRICE = TemplateField(key="price", field="price", type=TemplateFieldType.DECIMAL)
ORDER_DATE = TemplateField(
    key="order_date",
    field="order_date",
    type=TemplateFieldType.DATETIME,
)
EQUITY_TYPE_TX = TemplateField(
    key="type.equity",
    field="equity_type",
    type=TemplateFieldType.ENUM,
    enum=EquityType,
)
FUND_TYPE_TX = TemplateField(
    key="type.fund",
    field="fund_type",
    type=TemplateFieldType.ENUM,
    enum=FundType,
)
PORTFOLIO_NAME_TX = TemplateField(
    key="portfolio", field="portfolio_name", type=TemplateFieldType.TEXT
)

BASE_TX_FIELDS = [
    REFERENCE.require(),
    NAME.require(),
    AMOUNT.require(),
    CURRENCY.require(),
    TX_TYPE.require(),
    PRODUCT_TYPE.with_template(TemplateType.EXPORT),
    DATE.require(),
    ENTITY,
]

ACCOUNT_TX_FIELDS = FieldGroup(
    feature=Feature.TRANSACTIONS,
    product=ProductType.ACCOUNT,
    fields=BASE_TX_FIELDS
    + [
        FEES.default(Dezimal(0)),
        RETENTIONS.default(Dezimal(0)),
        INTEREST_RATE,
        AVERAGE_BALANCE,
        NET_AMOUNT,
    ],
)

STOCK_ETF_TX_FIELDS = FieldGroup(
    feature=Feature.TRANSACTIONS,
    product=ProductType.STOCK_ETF,
    fields=BASE_TX_FIELDS
    + [
        ISIN,
        TICKER,
        MARKET,
        SHARES.require(),
        PRICE.require(),
        FEES.default(Dezimal(0)),
        RETENTIONS.default(Dezimal(0)),
        ORDER_DATE,
        EQUITY_TYPE_TX,
        NET_AMOUNT,
    ],
)

FUND_TX_FIELDS = FieldGroup(
    feature=Feature.TRANSACTIONS,
    product=ProductType.FUND,
    fields=BASE_TX_FIELDS
    + [
        ISIN,
        MARKET,
        SHARES.require(),
        PRICE.require(),
        FEES.default(Dezimal(0)),
        RETENTIONS.default(Dezimal(0)),
        ORDER_DATE,
        FUND_TYPE_TX,
        NET_AMOUNT,
    ],
)

FUND_PORTFOLIO_TX_FIELDS = FieldGroup(
    feature=Feature.TRANSACTIONS,
    product=ProductType.FUND_PORTFOLIO,
    fields=BASE_TX_FIELDS
    + [
        PORTFOLIO_NAME_TX.require(),
        FEES.default(Dezimal(0)),
        IBAN,
    ],
)

FACTORING_TX_FIELDS = FieldGroup(
    feature=Feature.TRANSACTIONS,
    product=ProductType.FACTORING,
    fields=BASE_TX_FIELDS
    + [
        FEES.default(Dezimal(0)),
        RETENTIONS.default(Dezimal(0)),
        NET_AMOUNT,
    ],
)

REAL_ESTATE_CF_TX_FIELDS = FieldGroup(
    feature=Feature.TRANSACTIONS,
    product=ProductType.REAL_ESTATE_CF,
    fields=BASE_TX_FIELDS
    + [
        FEES.default(Dezimal(0)),
        RETENTIONS.default(Dezimal(0)),
        NET_AMOUNT,
    ],
)

DEPOSIT_TX_FIELDS = FieldGroup(
    feature=Feature.TRANSACTIONS,
    product=ProductType.DEPOSIT,
    fields=BASE_TX_FIELDS
    + [
        FEES.default(Dezimal(0)),
        RETENTIONS.default(Dezimal(0)),
        NET_AMOUNT,
    ],
)

ALIAS = TemplateField(key="alias", field="alias", type=TemplateFieldType.TEXT)
TARGET = TemplateField(key="target", field="target", type=TemplateFieldType.TEXT)
TARGET_NAME = TemplateField(
    key="target_name", field="target_name", type=TemplateFieldType.TEXT
)
TARGET_TYPE = TemplateField(
    key="target_type",
    field="target_type",
    type=TemplateFieldType.ENUM,
    enum=ContributionTargetType,
)
TARGET_SUBTYPE = TemplateField(
    key="target_subtype",
    field="target_subtype",
    type=TemplateFieldType.ENUM,
    enum=ContributionTargetSubtype,
)
FREQUENCY = TemplateField(
    key="frequency",
    field="frequency",
    type=TemplateFieldType.ENUM,
    enum=ContributionFrequency,
)
SINCE = TemplateField(key="since", field="since", type=TemplateFieldType.DATE)
UNTIL = TemplateField(key="until", field="until", type=TemplateFieldType.DATE)
NEXT_DATE = TemplateField(
    key="next_date", field="next_date", type=TemplateFieldType.DATE
)

PERIODIC_CONTRIBUTION_FIELDS = FieldGroup(
    feature=Feature.AUTO_CONTRIBUTIONS,
    product=None,
    fields=[
        ALIAS,
        TARGET.require(),
        TARGET_NAME.require(),
        TARGET_TYPE.require(),
        TARGET_SUBTYPE,
        AMOUNT.require(),
        CURRENCY.require(),
        FREQUENCY.require(),
        ACTIVE.require(),
        SINCE.require(),
        UNTIL,
        NEXT_DATE,
        ENTITY,
    ],
)

INVESTED = TemplateField(
    key="invested", field="invested", type=TemplateFieldType.DECIMAL
)
REPAID = TemplateField(key="repaid", field="repaid", type=TemplateFieldType.DECIMAL)
RETURNED = TemplateField(
    key="returned", field="returned", type=TemplateFieldType.DECIMAL
)
LAST_INVEST_DATE_HIST = TemplateField(
    key="last_invest_date",
    field="last_invest_date",
    type=TemplateFieldType.DATETIME,
)
LAST_TX_DATE = TemplateField(
    key="last_tx_date",
    field="last_tx_date",
    type=TemplateFieldType.DATETIME,
)
EFFECTIVE_MATURITY = TemplateField(
    key="effective_maturity",
    field="effective_maturity",
    type=TemplateFieldType.DATETIME,
)
NET_RETURN = TemplateField(
    key="net_return", field="net_return", type=TemplateFieldType.DECIMAL
)
INTERESTS = TemplateField(
    key="interests", field="interests", type=TemplateFieldType.DECIMAL
)

HISTORIC_BASE_FIELDS = [
    NAME.require(),
    PRODUCT_TYPE.require(),
    STATE.require(),
    INVESTED.require(),
    CURRENCY.require(),
    REPAID,
    RETURNED,
    LAST_INVEST_DATE_HIST.require(),
    LAST_TX_DATE.require(),
    EFFECTIVE_MATURITY,
    NET_RETURN,
    FEES,
    RETENTIONS,
    INTERESTS,
    ENTITY,
]

HISTORIC_FACTORING_FIELDS = FieldGroup(
    feature=Feature.HISTORIC,
    product=ProductType.FACTORING,
    fields=HISTORIC_BASE_FIELDS
    + [INTEREST_RATE, MATURITY.require(), FACTORING_TYPE.require()],
)

HISTORIC_REAL_ESTATE_CF_FIELDS = FieldGroup(
    feature=Feature.HISTORIC,
    product=ProductType.REAL_ESTATE_CF,
    fields=HISTORIC_BASE_FIELDS
    + [
        INTEREST_RATE,
        MATURITY.require(),
        EXTENDED_MATURITY,
        REAL_ESTATE_CF_TYPE.require(),
        BUSINESS_TYPE.require(),
    ],
)

ALL_TEMPLATE_FIELDS: dict[Feature, list[FieldGroup]] = {
    Feature.POSITION: [
        ACCOUNT_FIELDS,
        CARD_FIELDS,
        LOAN_FIELDS,
        STOCK_ETF_FIELDS,
        FUND_FIELDS,
        FACTORING_FIELDS,
        REAL_ESTATE_CF_FIELDS,
        DEPOSIT_FIELDS,
        CRYPTO_FIELDS,
    ],
    Feature.TRANSACTIONS: [
        ACCOUNT_TX_FIELDS,
        STOCK_ETF_TX_FIELDS,
        FUND_TX_FIELDS,
        FUND_PORTFOLIO_TX_FIELDS,
        FACTORING_TX_FIELDS,
        REAL_ESTATE_CF_TX_FIELDS,
        DEPOSIT_TX_FIELDS,
    ],
    Feature.AUTO_CONTRIBUTIONS: [PERIODIC_CONTRIBUTION_FIELDS],
    Feature.HISTORIC: [
        HISTORIC_FACTORING_FIELDS,
        HISTORIC_REAL_ESTATE_CF_FIELDS,
    ],
}

TEMPLATE_FIELD_MATRIX: dict[
    Feature, dict[Optional[ProductType], list[TemplateField]]
] = {}
for feature, groups in ALL_TEMPLATE_FIELDS.items():
    TEMPLATE_FIELD_MATRIX[feature] = {}
    for group in groups:
        TEMPLATE_FIELD_MATRIX[feature][group.product] = group.fields

FIELDS_BY_NAME: dict[str, list[TemplateField]] = {}
for groups in ALL_TEMPLATE_FIELDS.values():
    for group in groups:
        for field in group.fields:
            if field.field not in FIELDS_BY_NAME:
                FIELDS_BY_NAME[field.field] = []
            FIELDS_BY_NAME[field.field].append(field)
