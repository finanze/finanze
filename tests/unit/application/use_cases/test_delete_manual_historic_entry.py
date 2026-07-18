from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from application.use_cases.delete_manual_historic_entry import (
    DeleteManualHistoricEntryImpl,
)
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.exception.exceptions import ManualHistoricEntryNotFound
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.historic import (
    DeleteManualHistoricEntryRequest,
    FactoringEntry,
    HistoricState,
    HistoricTxDeletion,
)
from domain.transactions import FactoringTx, Transactions, TxType


class _NoopTransaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *args):
        return False


def _make_transaction_handler():
    handler = MagicMock()
    handler.start = MagicMock(return_value=_NoopTransaction())
    return handler


def _make_entity():
    return Entity(
        id=uuid4(),
        name="Manual",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )


def _make_tx(entity, tx_date, tx_type=TxType.REPAYMENT, ref=None):
    return FactoringTx(
        id=uuid4(),
        ref=ref or f"manual-{uuid4().hex}",
        name="Loan A",
        amount=Dezimal("100"),
        currency="EUR",
        type=tx_type,
        date=tx_date,
        entity=entity,
        source=DataSource.MANUAL,
        product_type=ProductType.FACTORING,
        fees=Dezimal(0),
        retentions=Dezimal(0),
        net_amount=Dezimal("100"),
    )


def _make_settled_entry(entity, related_txs, maturity):
    return FactoringEntry(
        id=uuid4(),
        name="Loan A",
        invested=Dezimal("1000"),
        repaid=Dezimal("1000"),
        returned=Dezimal("1100"),
        currency="EUR",
        last_invest_date=datetime(2024, 1, 1, tzinfo=tzlocal()),
        last_tx_date=maturity,
        effective_maturity=maturity,
        net_return=Dezimal("100"),
        fees=Dezimal(0),
        retentions=Dezimal(0),
        interests=Dezimal("100"),
        state=HistoricState.COMPLETED.value,
        entity=entity,
        product_type=ProductType.FACTORING,
        related_txs=related_txs,
        entity_account_id=None,
        source=DataSource.MANUAL,
        manual_key="key-1",
        interest_rate=Dezimal("0.1"),
        gross_interest_rate=Dezimal("0.1"),
        maturity=date(2024, 12, 31),
        type="SIMPLE",
    )


def _build_uc(entry):
    historic_port = AsyncMock()
    historic_port.get_by_id.return_value = entry

    transaction_port = AsyncMock()
    transaction_port.get_by_entity_and_source.return_value = Transactions(
        investment=[], account=[]
    )

    registry = AsyncMock()
    registry.get_last_import_records.return_value = []

    uc = DeleteManualHistoricEntryImpl(
        historic_port=historic_port,
        transaction_port=transaction_port,
        virtual_import_registry=registry,
        transaction_handler_port=_make_transaction_handler(),
    )
    return uc, {"historic_port": historic_port, "transaction_port": transaction_port}


@pytest.mark.asyncio
async def test_delete_none_keeps_txs():
    entity = _make_entity()
    maturity = datetime(2024, 12, 31, tzinfo=tzlocal())
    txs = [_make_tx(entity, maturity)]
    entry = _make_settled_entry(entity, txs, maturity)
    uc, mocks = _build_uc(entry)

    await uc.execute(
        DeleteManualHistoricEntryRequest(
            entry_id=entry.id, tx_deletion=HistoricTxDeletion.NONE
        )
    )

    mocks["transaction_port"].delete_by_id.assert_not_awaited()
    mocks["historic_port"].delete_by_id.assert_awaited_once_with(entry.id)


@pytest.mark.asyncio
async def test_delete_all_removes_all_txs():
    entity = _make_entity()
    maturity = datetime(2024, 12, 31, tzinfo=tzlocal())
    txs = [
        _make_tx(entity, datetime(2024, 6, 1, tzinfo=tzlocal())),
        _make_tx(entity, maturity),
    ]
    entry = _make_settled_entry(entity, txs, maturity)
    uc, mocks = _build_uc(entry)

    await uc.execute(
        DeleteManualHistoricEntryRequest(
            entry_id=entry.id, tx_deletion=HistoricTxDeletion.ALL
        )
    )

    assert mocks["transaction_port"].delete_by_id.await_count == 2
    mocks["historic_port"].delete_by_id.assert_awaited_once_with(entry.id)


@pytest.mark.asyncio
async def test_delete_settlement_only_removes_maturity_txs():
    entity = _make_entity()
    maturity = datetime(2024, 12, 31, tzinfo=tzlocal())
    partial = _make_tx(entity, datetime(2024, 6, 1, tzinfo=tzlocal()))
    settlement = _make_tx(entity, maturity)
    entry = _make_settled_entry(entity, [partial, settlement], maturity)
    uc, mocks = _build_uc(entry)

    await uc.execute(
        DeleteManualHistoricEntryRequest(
            entry_id=entry.id, tx_deletion=HistoricTxDeletion.SETTLEMENT
        )
    )

    mocks["transaction_port"].delete_by_id.assert_awaited_once_with(settlement.id)
    mocks["historic_port"].delete_by_id.assert_awaited_once_with(entry.id)


@pytest.mark.asyncio
async def test_delete_settlement_keeps_same_day_amortization():
    from application.use_cases.manual_historic_common import settlement_tx_ref

    entity = _make_entity()
    maturity = datetime(2024, 12, 31, tzinfo=tzlocal())
    amortization = _make_tx(entity, maturity)
    settlement = _make_tx(entity, maturity, ref=settlement_tx_ref())
    entry = _make_settled_entry(entity, [amortization, settlement], maturity)
    uc, mocks = _build_uc(entry)

    await uc.execute(
        DeleteManualHistoricEntryRequest(
            entry_id=entry.id, tx_deletion=HistoricTxDeletion.SETTLEMENT
        )
    )

    mocks["transaction_port"].delete_by_id.assert_awaited_once_with(settlement.id)
    mocks["historic_port"].delete_by_id.assert_awaited_once_with(entry.id)
    entity = _make_entity()
    entry = _make_settled_entry(entity, [], datetime.now(tzlocal()))
    uc, mocks = _build_uc(entry)
    mocks["historic_port"].get_by_id.return_value = None

    with pytest.raises(ManualHistoricEntryNotFound):
        await uc.execute(
            DeleteManualHistoricEntryRequest(
                entry_id=uuid4(), tx_deletion=HistoricTxDeletion.NONE
            )
        )


@pytest.mark.asyncio
async def test_delete_rejects_non_manual():
    entity = _make_entity()
    entry = _make_settled_entry(entity, [], datetime.now(tzlocal()))
    entry.source = DataSource.REAL
    uc, mocks = _build_uc(entry)

    with pytest.raises(ManualHistoricEntryNotFound):
        await uc.execute(
            DeleteManualHistoricEntryRequest(
                entry_id=entry.id, tx_deletion=HistoricTxDeletion.NONE
            )
        )
