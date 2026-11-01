from datetime import date, datetime
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.settlement import match_settlements, settlement_window
from domain.transactions import AccountTx, FundTx, StockTx, TxType

ENTITY = Entity(
    id=uuid4(),
    name="Bank",
    natural_id=None,
    type=EntityType.FINANCIAL_INSTITUTION,
    origin=EntityOrigin.NATIVE,
    icon_url=None,
)


def _fund_buy(ref: str, when: datetime) -> FundTx:
    return FundTx(
        id=uuid4(),
        ref=ref,
        name="Buy fund",
        amount=Dezimal("1000"),
        net_amount=Dezimal("1000"),
        currency="EUR",
        type=TxType.BUY,
        date=when,
        entity=ENTITY,
        source=DataSource.REAL,
        product_type=ProductType.FUND,
        isin="LU0000000001",
        shares=Dezimal("10"),
        price=Dezimal("100"),
        fees=Dezimal(0),
    )


def _outflow(when: datetime) -> AccountTx:
    return AccountTx(
        id=uuid4(),
        ref=str(uuid4()),
        name="Fund subscription",
        amount=Dezimal("1000"),
        currency="EUR",
        type=TxType.OUTFLOW,
        date=when,
        entity=ENTITY,
        source=DataSource.REAL,
        product_type=ProductType.ACCOUNT,
        fees=Dezimal(0),
        retentions=Dezimal(0),
    )


def test_matches_aware_account_tx_with_naive_investment_tx():
    account_tx = _outflow(datetime(2026, 9, 22, 9, tzinfo=tzlocal()))
    investment_tx = _fund_buy("FUND-1", datetime(2026, 9, 21, 10))

    links = match_settlements([account_tx], [investment_tx], set())

    assert links == {account_tx.id: "FUND-1"}


def test_settlement_window_accepts_mixed_naive_and_aware_dates():
    window = settlement_window(
        [
            _fund_buy("FUND-1", datetime(2026, 9, 21, 10)),
            _fund_buy("FUND-2", datetime(2026, 9, 25, 10, tzinfo=tzlocal())),
        ]
    )

    assert window.from_date == date(2026, 9, 16)
    assert window.to_date == date(2026, 9, 30)


def _dividend_pair():
    cash = _outflow(datetime(2026, 10, 23, 12, tzinfo=tzlocal()))
    cash.type = TxType.INFLOW
    cash.amount = Dezimal("0.08")
    cash.entity_account_id = uuid4()
    dividend = StockTx(
        id=uuid4(),
        ref="dividend:security:cash-ref",
        name="ETF dividend",
        amount=Dezimal("0.10"),
        net_amount=Dezimal("0.08"),
        currency="EUR",
        type=TxType.DIVIDEND,
        date=cash.date,
        entity=ENTITY,
        entity_account_id=cash.entity_account_id,
        source=DataSource.REAL,
        product_type=ProductType.STOCK_ETF,
        price=Dezimal(0),
        fees=Dezimal(0),
        retentions=Dezimal("0.02"),
        linked_tx=cash.ref,
    )
    return cash, dividend


def test_explicit_dividend_hint_wins_over_equal_generic_candidate():
    cash, dividend = _dividend_pair()
    generic = _fund_buy("generic-sale", cash.date)
    generic.type = TxType.SELL
    generic.amount = generic.net_amount = cash.amount

    assert match_settlements([cash], [generic, dividend], set()) == {
        cash.id: dividend.ref
    }


@pytest.mark.parametrize(
    "mismatch",
    [
        "cash-ref",
        "entity-account",
        "missing-account",
        "amount",
        "currency",
        "direction",
        "date",
        "entity",
    ],
)
def test_explicit_dividend_hint_never_falls_back_to_another_cash_leg(mismatch):
    cash, dividend = _dividend_pair()
    if mismatch == "cash-ref":
        cash.ref = "unrelated-cash"
    elif mismatch == "entity-account":
        cash.entity_account_id = uuid4()
    elif mismatch == "missing-account":
        cash.entity_account_id = None
    elif mismatch == "amount":
        cash.amount = Dezimal("0.09")
    elif mismatch == "currency":
        cash.currency = "USD"
    elif mismatch == "direction":
        cash.type = TxType.OUTFLOW
    elif mismatch == "date":
        cash.date = datetime(2026, 9, 1, tzinfo=tzlocal())
    elif mismatch == "entity":
        cash.entity = Entity(
            id=uuid4(),
            name="Other bank",
            natural_id=None,
            type=EntityType.FINANCIAL_INSTITUTION,
            origin=EntityOrigin.NATIVE,
            icon_url=None,
        )

    assert match_settlements([cash], [dividend], set()) == {}


@pytest.mark.parametrize("state", ["locked", "linked", "taken"])
def test_explicit_dividend_hint_respects_existing_classifications(state):
    cash, dividend = _dividend_pair()
    taken = set()
    if state == "locked":
        cash.labels_locked = True
    elif state == "linked":
        cash.linked_tx = "existing-investment"
    else:
        taken.add((ENTITY.id, dividend.ref))

    assert match_settlements([cash], [dividend], taken) == {}


def test_explicit_dividend_hint_refuses_duplicate_cash_references():
    cash, dividend = _dividend_pair()
    other_cash, _ = _dividend_pair()
    other_cash.ref = cash.ref
    other_cash.entity_account_id = cash.entity_account_id

    assert match_settlements([cash, other_cash], [dividend], set()) == {}
