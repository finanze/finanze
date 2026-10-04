from datetime import date, datetime
from uuid import uuid4

from dateutil.tz import tzlocal

from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.settlement import match_settlements, settlement_window
from domain.transactions import AccountTx, FundTx, TxType

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
