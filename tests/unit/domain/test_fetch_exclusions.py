from uuid import uuid4

import pytest
from pydantic import ValidationError

from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.fetch_exclusions import FetchExclusions
from domain.fetch_record import DataSource
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    Card,
    Cards,
    CardType,
    FundDetail,
    FundInvestments,
    FundPortfolio,
    FundPortfolios,
    FundType,
    GlobalPosition,
    ProductType,
)
from domain.native_entities import INDEXA_CAPITAL
from domain.settings import AccountAssetConfig, AccountExclusion
from domain.transactions import (
    AccountTx,
    FundPortfolioTx,
    StockTx,
    Transactions,
    TxType,
)
from infrastructure.repository.settings.settings_mapper import parse_section

IBAN = "ES1234567890"


def _account(iban):
    return Account(
        id=uuid4(),
        total=Dezimal(100),
        currency="EUR",
        type=AccountType.CHECKING,
        iban=iban,
    )


def _tx(ref, iban=None, linked_tx=None):
    return AccountTx(
        id=uuid4(),
        ref=ref,
        name=ref,
        amount=Dezimal(10),
        currency="EUR",
        type=TxType.INFLOW,
        date="2026-11-08T10:00:00+01:00",
        entity=INDEXA_CAPITAL,
        source=DataSource.REAL,
        product_type=ProductType.ACCOUNT,
        fees=Dezimal(0),
        retentions=Dezimal(0),
        iban=iban,
        linked_tx=linked_tx,
    )


def _fund(portfolio):
    return FundDetail(
        id=uuid4(),
        name="Fund",
        isin="ISIN1",
        market=None,
        shares=Dezimal(1),
        market_value=Dezimal(100),
        currency="EUR",
        type=FundType.MUTUAL_FUND,
        initial_investment=Dezimal(100),
        portfolio=portfolio,
    )


def test_normalization_validation_and_duplicates():
    rule = AccountExclusion(type="IBAN", value=" es12 3456 7890 ")
    assert rule.value == IBAN
    for value in ("", "  ", "ES12-34", "A" * 35, "é123", None):
        with pytest.raises(ValidationError):
            AccountExclusion(type="IBAN", value=value)
    with pytest.raises(ValidationError):
        AccountExclusion(type="REGEX", value=IBAN)
    with pytest.raises(ValidationError):
        AccountAssetConfig(
            exclusions=[rule, {"type": "IBAN", "value": "es12 3456 7890"}]
        )


def test_exact_matching_and_legacy_settings_default():
    exclusions = FetchExclusions([AccountExclusion(type="IBAN", value=IBAN)])
    assert exclusions.matches(" es12 3456 7890 ")
    assert not exclusions.matches(None)
    assert not exclusions.matches("ES123456")
    assert not exclusions.matches(IBAN + "1")
    settings = parse_section("assets", {"crypto": {"stablecoins": ["USDT"]}})
    assert settings.accounts.exclusions == []
    assert settings.crypto.stablecoins == ["USDT"]


def test_position_cascade_uses_physical_links_not_isins():
    excluded, included, unidentified = _account(IBAN), _account("ES999"), _account(None)
    excluded_portfolio = FundPortfolio(id=uuid4(), account_id=excluded.id)
    included_portfolio = FundPortfolio(id=uuid4(), account_id=included.id)
    excluded_fund = _fund(FundPortfolio(id=excluded_portfolio.id))
    included_fund = _fund(FundPortfolio(id=included_portfolio.id))
    standalone = _fund(None)
    excluded_card = Card(
        id=uuid4(),
        currency="EUR",
        type=CardType.DEBIT,
        used=Dezimal(0),
        related_account=excluded.id,
    )
    included_card = Card(
        id=uuid4(),
        currency="EUR",
        type=CardType.DEBIT,
        used=Dezimal(0),
        related_account=included.id,
    )
    position = GlobalPosition(
        id=uuid4(),
        entity=INDEXA_CAPITAL,
        products={
            ProductType.ACCOUNT: Accounts([excluded, included, unidentified]),
            ProductType.CARD: Cards([excluded_card, included_card]),
            ProductType.FUND_PORTFOLIO: FundPortfolios(
                [excluded_portfolio, included_portfolio]
            ),
            ProductType.FUND: FundInvestments(
                [excluded_fund, included_fund, standalone]
            ),
        },
    )
    FetchExclusions([AccountExclusion(type="IBAN", value=IBAN)]).apply_to_position(
        position
    )
    assert position.products[ProductType.ACCOUNT].entries == [included, unidentified]
    assert position.products[ProductType.CARD].entries == [included_card]
    assert position.products[ProductType.FUND_PORTFOLIO].entries == [included_portfolio]
    assert position.products[ProductType.FUND].entries == [included_fund, standalone]


def test_embedded_portfolio_account_and_empty_snapshot():
    account = _account(IBAN)
    portfolio = FundPortfolio(id=uuid4(), account=account)
    position = GlobalPosition(
        id=uuid4(),
        entity=INDEXA_CAPITAL,
        products={
            ProductType.ACCOUNT: Accounts([account]),
            ProductType.FUND: FundInvestments([_fund(portfolio)]),
        },
    )
    FetchExclusions([AccountExclusion(type="IBAN", value=IBAN)]).apply_to_position(
        position
    )
    assert position.products[ProductType.ACCOUNT].entries == []
    assert position.products[ProductType.FUND].entries == []


def test_transactions_only_cascade_via_explicit_refs():
    cash = _tx("excluded-cash", "es12 3456 7890", "stock")
    stock = StockTx(
        id=uuid4(),
        ref="stock",
        name="Stock",
        amount=Dezimal(10),
        price=Dezimal(10),
        fees=Dezimal(0),
        currency="EUR",
        type=TxType.BUY,
        date=cash.date,
        entity=INDEXA_CAPITAL,
        source=DataSource.REAL,
        product_type=ProductType.STOCK_ETF,
    )
    unlinked = StockTx(**{**stock.__dict__, "id": uuid4(), "ref": "other"})
    portfolio_fee = FundPortfolioTx(
        id=uuid4(),
        ref="fee",
        name="Fee",
        amount=Dezimal(1),
        currency="EUR",
        type=TxType.FEE,
        date=cash.date,
        entity=INDEXA_CAPITAL,
        source=DataSource.REAL,
        product_type=ProductType.FUND_PORTFOLIO,
        portfolio_name="Portfolio",
        iban=IBAN,
    )
    included, unidentified = _tx("included", "ES999"), _tx("unknown")
    transactions = Transactions(
        account=[cash, included, unidentified],
        investment=[stock, unlinked, portfolio_fee],
    )
    FetchExclusions([AccountExclusion(type="IBAN", value=IBAN)]).apply_to_transactions(
        transactions
    )
    assert transactions.account == [included, unidentified]
    assert transactions.investment == [unlinked]


def test_transaction_refs_are_scoped_by_entity():
    cash = _tx("cash", IBAN, "same-ref")
    other = _tx("same-ref", "ES999")
    other.entity = Entity(
        id=uuid4(),
        name="Other",
        type=INDEXA_CAPITAL.type,
        origin=INDEXA_CAPITAL.origin,
        natural_id=None,
        icon_url=None,
    )
    transactions = Transactions(account=[cash, other])
    FetchExclusions([AccountExclusion(type="IBAN", value=IBAN)]).apply_to_transactions(
        transactions
    )
    assert transactions.account == [other]


def test_investment_link_to_excluded_cash_is_not_inferred_for_other_entities():
    cash = _tx("cash", IBAN)
    linked = StockTx(
        id=uuid4(),
        ref="stock",
        name="Stock",
        amount=Dezimal(10),
        price=Dezimal(10),
        fees=Dezimal(0),
        currency="EUR",
        type=TxType.BUY,
        date=cash.date,
        entity=INDEXA_CAPITAL,
        source=DataSource.REAL,
        product_type=ProductType.STOCK_ETF,
        linked_tx=cash.ref,
    )
    other = StockTx(**{**linked.__dict__, "id": uuid4()})
    other.entity = Entity(
        id=uuid4(),
        name="Other",
        type=INDEXA_CAPITAL.type,
        origin=INDEXA_CAPITAL.origin,
        natural_id=None,
        icon_url=None,
    )
    transactions = Transactions(account=[cash], investment=[linked, other])
    FetchExclusions([AccountExclusion(type="IBAN", value=IBAN)]).apply_to_transactions(
        transactions
    )
    assert transactions.account == []
    assert transactions.investment == [other]
