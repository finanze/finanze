from datetime import datetime
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.transactions import AccountTx, TxType, account_balance_delta


def _make_tx(
    tx_type: TxType,
    amount: str = "100",
    fees: str = "0",
    retentions: str = "0",
) -> AccountTx:
    entity = Entity(
        id=uuid4(),
        name="Bank",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )
    return AccountTx(
        id=uuid4(),
        ref="REF-1",
        name="Tx",
        amount=Dezimal(amount),
        currency="EUR",
        type=tx_type,
        date=datetime(2025, 1, 1, 12, tzinfo=tzlocal()),
        entity=entity,
        source=DataSource.MANUAL,
        product_type=ProductType.ACCOUNT,
        fees=Dezimal(fees),
        retentions=Dezimal(retentions),
    )


def test_inflow_adds_net_amount():
    tx = _make_tx(TxType.INFLOW, amount="100", fees="2.50")
    assert account_balance_delta(tx) == Dezimal("97.50")


def test_interest_adds_net_after_fees_and_retentions():
    tx = _make_tx(TxType.INTEREST, amount="100", fees="1", retentions="19")
    assert account_balance_delta(tx) == Dezimal("80")


def test_outflow_subtracts_amount_plus_fees():
    tx = _make_tx(TxType.OUTFLOW, amount="100", fees="3")
    assert account_balance_delta(tx) == Dezimal("-103")


@pytest.mark.parametrize("fees", ["15", "0"])
def test_fee_subtracts_amount_once(fees: str):
    tx = _make_tx(TxType.FEE, amount="15", fees=fees)
    assert account_balance_delta(tx) == Dezimal("-15")


@pytest.mark.parametrize("tx_type", [TxType.TRANSFER_IN, TxType.BUY])
def test_unsupported_type_raises(tx_type: TxType):
    tx = _make_tx(tx_type)
    with pytest.raises(ValueError, match="Unsupported account transaction type"):
        account_balance_delta(tx)
