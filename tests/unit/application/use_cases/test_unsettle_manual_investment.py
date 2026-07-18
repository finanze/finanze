from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from application.use_cases.manual_historic_common import (
    SETTLEMENT_TX_REF_PREFIX,
)
from application.use_cases.unsettle_manual_investment import (
    RESTORED_STATE,
    UnsettleManualInvestmentImpl,
)
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType, Feature
from domain.exception.exceptions import (
    ManualHistoricEntryNotFinal,
    ManualHistoricEntryNotFound,
    ManualInvestmentNotFound,
)
from domain.fetch_record import DataSource
from domain.global_position import (
    FactoringInvestments,
    GlobalPosition,
    ProductType,
)
from domain.historic import (
    FactoringEntry,
    HistoricState,
    UnsettleManualInvestmentRequest,
)
from domain.transactions import FactoringTx, Transactions, TxType
from domain.virtual_data import VirtualDataImport, VirtualDataSource


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


def _make_tx(entity, tx_date, amount, tx_type, ref=None):
    return FactoringTx(
        id=uuid4(),
        ref=ref or f"manual-{uuid4().hex}",
        name="Loan A",
        amount=amount,
        currency="EUR",
        type=tx_type,
        date=tx_date,
        entity=entity,
        source=DataSource.MANUAL,
        product_type=ProductType.FACTORING,
        fees=Dezimal(0),
        retentions=Dezimal(0),
        net_amount=amount,
    )


def _make_settlement_tx(entity, tx_date, amount, tx_type):
    return _make_tx(
        entity,
        tx_date,
        amount,
        tx_type,
        ref=f"{SETTLEMENT_TX_REF_PREFIX}{uuid4().hex}",
    )


def _make_settled_entry(entity, related_txs, maturity, state=None):
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
        state=state or HistoricState.COMPLETED.value,
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


def _build_uc(entry, position=None):
    historic_port = AsyncMock()
    historic_port.get_by_id.return_value = entry

    position_port = AsyncMock()
    position_port.get_by_id.return_value = position

    transaction_port = AsyncMock()
    transaction_port.get_by_entity_and_source.return_value = Transactions(
        investment=[], account=[]
    )

    registry = AsyncMock()
    if position is not None:
        registry.get_last_import_records.return_value = [
            VirtualDataImport(
                import_id=uuid4(),
                global_position_id=position.id,
                source=VirtualDataSource.MANUAL,
                date=datetime.now(tzlocal()),
                feature=Feature.POSITION,
                entity_id=entry.entity.id,
            )
        ]
    else:
        registry.get_last_import_records.return_value = []

    snapshot_writer = AsyncMock()

    uc = UnsettleManualInvestmentImpl(
        historic_port=historic_port,
        position_port=position_port,
        transaction_port=transaction_port,
        virtual_import_registry=registry,
        snapshot_writer=snapshot_writer,
        transaction_handler_port=_make_transaction_handler(),
    )
    return uc, {
        "historic_port": historic_port,
        "position_port": position_port,
        "transaction_port": transaction_port,
        "snapshot_writer": snapshot_writer,
    }


def _make_manual_position(entity):
    return GlobalPosition(
        id=uuid4(),
        entity=entity,
        source=DataSource.MANUAL,
        products={ProductType.FACTORING: FactoringInvestments(entries=[])},
    )


@pytest.mark.asyncio
async def test_unsettle_restores_position_and_removes_settlement_txs():
    entity = _make_entity()
    maturity = datetime(2024, 12, 31, tzinfo=tzlocal())
    kept_repay = _make_tx(entity, maturity, Dezimal("400"), TxType.REPAYMENT)
    settle_repay = _make_settlement_tx(
        entity, maturity, Dezimal("600"), TxType.REPAYMENT
    )
    settle_interest = _make_settlement_tx(
        entity, maturity, Dezimal("100"), TxType.INTEREST
    )
    entry = _make_settled_entry(
        entity, [kept_repay, settle_repay, settle_interest], maturity
    )
    position = _make_manual_position(entity)
    uc, mocks = _build_uc(entry, position)

    await uc.execute(_request(entry.id))

    deleted_ids = {
        c.args[0] for c in mocks["transaction_port"].delete_by_id.await_args_list
    }
    assert deleted_ids == {settle_repay.id, settle_interest.id}

    mocks["snapshot_writer"].write.assert_awaited_once()
    written_position = mocks["snapshot_writer"].write.await_args.args[1]
    container = written_position.products[ProductType.FACTORING]
    assert len(container.entries) == 1
    detail = container.entries[0]
    assert detail.state == RESTORED_STATE
    assert detail.amount == Dezimal("1000")

    mocks["historic_port"].upsert.assert_awaited_once()
    ongoing = mocks["historic_port"].upsert.await_args.args[0]
    assert ongoing.state == RESTORED_STATE
    assert ongoing.effective_maturity is None
    assert ongoing.related_txs == [kept_repay]


@pytest.mark.asyncio
async def test_unsettle_not_found():
    entity = _make_entity()
    entry = _make_settled_entry(entity, [], datetime.now(tzlocal()))
    uc, mocks = _build_uc(entry)
    mocks["historic_port"].get_by_id.return_value = None

    with pytest.raises(ManualHistoricEntryNotFound):
        await uc.execute(_request(uuid4()))


@pytest.mark.asyncio
async def test_unsettle_rejects_non_final():
    entity = _make_entity()
    entry = _make_settled_entry(
        entity, [], datetime.now(tzlocal()), state="OUTSTANDING"
    )
    uc, _ = _build_uc(entry)

    with pytest.raises(ManualHistoricEntryNotFinal):
        await uc.execute(_request(entry.id))


@pytest.mark.asyncio
async def test_unsettle_without_manual_position_raises():
    entity = _make_entity()
    maturity = datetime(2024, 12, 31, tzinfo=tzlocal())
    entry = _make_settled_entry(
        entity,
        [_make_tx(entity, maturity, Dezimal("1000"), TxType.REPAYMENT)],
        maturity,
    )
    uc, _ = _build_uc(entry, position=None)

    with pytest.raises(ManualInvestmentNotFound):
        await uc.execute(_request(entry.id))


def _request(entry_id):
    return UnsettleManualInvestmentRequest(entry_id=entry_id)
