from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from application.use_cases.manual_historic_common import (
    make_investment_tx,
)
from application.use_cases.settle_manual_investment import SettleManualInvestmentImpl
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType, Feature
from domain.exception.exceptions import EntityNotFound, ManualInvestmentNotFound
from domain.fetch_record import DataSource
from domain.global_position import (
    FactoringDetail,
    FactoringInvestments,
    GlobalPosition,
    ProductType,
    RealEstateCFDetail,
    RealEstateCFInvestments,
)
from domain.historic import HistoricState, SettleManualInvestmentRequest
from domain.transactions import Transactions, TxType
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


def _make_factoring(entry_id=None):
    return FactoringDetail(
        id=entry_id or uuid4(),
        name="Loan A",
        amount=Dezimal("1000"),
        currency="EUR",
        interest_rate=Dezimal("0.1"),
        start=datetime(2024, 1, 1, tzinfo=tzlocal()),
        maturity=date(2024, 12, 31),
        type="SIMPLE",
        state="OUTSTANDING",
    )


def _make_position(entity, factoring):
    return GlobalPosition(
        id=uuid4(),
        entity=entity,
        products={ProductType.FACTORING: FactoringInvestments(entries=[factoring])},
    )


def _make_recf(entry_id=None, pending="700"):
    return RealEstateCFDetail(
        id=entry_id or uuid4(),
        name="Project X",
        amount=Dezimal("1000"),
        pending_amount=Dezimal(pending),
        currency="EUR",
        interest_rate=Dezimal("0.1"),
        start=datetime(2024, 1, 1, tzinfo=tzlocal()),
        maturity=date(2024, 12, 31),
        type="LOAN",
        state="OUTSTANDING",
    )


def _make_recf_position(entity, recf):
    return GlobalPosition(
        id=uuid4(),
        entity=entity,
        products={ProductType.REAL_ESTATE_CF: RealEstateCFInvestments(entries=[recf])},
    )


def _make_registry(entity, position):
    registry = AsyncMock()
    registry.get_last_import_records.return_value = [
        VirtualDataImport(
            import_id=uuid4(),
            global_position_id=position.id,
            source=VirtualDataSource.MANUAL,
            date=datetime.now(tzlocal()),
            feature=Feature.POSITION,
            entity_id=entity.id,
        )
    ]
    return registry


def _build_uc(entity, position, historic_port=None):
    entity_port = AsyncMock()
    entity_port.get_by_id.return_value = entity

    position_port = AsyncMock()
    position_port.get_by_id.return_value = position

    transaction_port = AsyncMock()
    transaction_port.get_by_entity_and_source.return_value = Transactions(
        investment=[], account=[]
    )

    if historic_port is None:
        historic_port = AsyncMock()
        historic_port.get_by_manual_key.return_value = None

    registry = _make_registry(entity, position)
    snapshot_writer = AsyncMock()

    uc = SettleManualInvestmentImpl(
        entity_port=entity_port,
        position_port=position_port,
        transaction_port=transaction_port,
        historic_port=historic_port,
        virtual_import_registry=registry,
        snapshot_writer=snapshot_writer,
        transaction_handler_port=_make_transaction_handler(),
    )
    return uc, {
        "entity_port": entity_port,
        "position_port": position_port,
        "transaction_port": transaction_port,
        "historic_port": historic_port,
        "registry": registry,
        "snapshot_writer": snapshot_writer,
    }


@pytest.mark.asyncio
async def test_settle_completed_creates_repayment_and_interest_txs():
    entity = _make_entity()
    factoring = _make_factoring()
    position = _make_position(entity, factoring)
    uc, mocks = _build_uc(entity, position)

    request = SettleManualInvestmentRequest(
        entity_id=entity.id,
        entry_id=factoring.id,
        product_type=ProductType.FACTORING,
        interests=Dezimal("100"),
        fees=Dezimal("5"),
        retentions=Dezimal("19"),
    )

    await uc.execute(request)

    mocks["transaction_port"].save.assert_awaited_once()
    saved = mocks["transaction_port"].save.await_args.args[0]
    txs = saved.investment
    assert {t.type for t in txs} == {TxType.REPAYMENT, TxType.INTEREST}

    repayment = next(t for t in txs if t.type == TxType.REPAYMENT)
    interest = next(t for t in txs if t.type == TxType.INTEREST)
    assert repayment.amount == Dezimal("1000")
    assert interest.amount == Dezimal("100")
    assert interest.fees == Dezimal("5")
    assert interest.retentions == Dezimal("19")


@pytest.mark.asyncio
async def test_settle_completed_finalizes_historic_and_removes_entry():
    entity = _make_entity()
    factoring = _make_factoring()
    position = _make_position(entity, factoring)
    uc, mocks = _build_uc(entity, position)

    request = SettleManualInvestmentRequest(
        entity_id=entity.id,
        entry_id=factoring.id,
        product_type=ProductType.FACTORING,
        interests=Dezimal("100"),
    )

    await uc.execute(request)

    mocks["historic_port"].upsert.assert_awaited_once()
    finalized = mocks["historic_port"].upsert.await_args.args[0]
    assert finalized.state == HistoricState.COMPLETED.value
    assert finalized.effective_maturity is not None
    assert finalized.source == DataSource.MANUAL

    mocks["snapshot_writer"].write.assert_awaited_once()
    written_position = mocks["snapshot_writer"].write.await_args.args[1]
    entries = written_position.products[ProductType.FACTORING].entries
    assert all(e.id != factoring.id for e in entries)


@pytest.mark.asyncio
async def test_settle_with_pending_capital_marks_defaulted():
    entity = _make_entity()
    factoring = _make_factoring()
    position = _make_position(entity, factoring)
    uc, mocks = _build_uc(entity, position)

    request = SettleManualInvestmentRequest(
        entity_id=entity.id,
        entry_id=factoring.id,
        product_type=ProductType.FACTORING,
        interests=Dezimal("0"),
        pending_capital=Dezimal("400"),
    )

    await uc.execute(request)

    finalized = mocks["historic_port"].upsert.await_args.args[0]
    assert finalized.state == HistoricState.DEFAULTED.value

    saved = mocks["transaction_port"].save.await_args.args[0]
    repayment = next(t for t in saved.investment if t.type == TxType.REPAYMENT)
    assert repayment.amount == Dezimal("600")


@pytest.mark.asyncio
async def test_settle_default_interests_computed_from_profitability():
    entity = _make_entity()
    factoring = _make_factoring()
    position = _make_position(entity, factoring)
    uc, mocks = _build_uc(entity, position)

    request = SettleManualInvestmentRequest(
        entity_id=entity.id,
        entry_id=factoring.id,
        product_type=ProductType.FACTORING,
    )

    await uc.execute(request)

    expected = round(factoring.amount * factoring.profitability, 2)
    saved = mocks["transaction_port"].save.await_args.args[0]
    interest_txs = [t for t in saved.investment if t.type == TxType.INTEREST]
    if expected > Dezimal(0):
        assert interest_txs[0].amount == expected
    else:
        assert interest_txs == []


@pytest.mark.asyncio
async def test_settle_default_interests_over_repaid_capital():
    entity = _make_entity()
    factoring = _make_factoring()
    position = _make_position(entity, factoring)
    uc, mocks = _build_uc(entity, position)

    request = SettleManualInvestmentRequest(
        entity_id=entity.id,
        entry_id=factoring.id,
        product_type=ProductType.FACTORING,
        pending_capital=Dezimal("400"),
    )

    await uc.execute(request)

    repaid = Dezimal("600")
    expected = round(repaid * factoring.profitability, 2)
    saved = mocks["transaction_port"].save.await_args.args[0]
    repayment = next(t for t in saved.investment if t.type == TxType.REPAYMENT)
    assert repayment.amount == repaid
    interest_txs = [t for t in saved.investment if t.type == TxType.INTEREST]
    if expected > Dezimal(0):
        assert interest_txs[0].amount == expected


@pytest.mark.asyncio
async def test_settle_entity_not_found():
    entity = _make_entity()
    factoring = _make_factoring()
    position = _make_position(entity, factoring)
    uc, mocks = _build_uc(entity, position)
    mocks["entity_port"].get_by_id.return_value = None

    request = SettleManualInvestmentRequest(
        entity_id=entity.id,
        entry_id=factoring.id,
        product_type=ProductType.FACTORING,
    )

    with pytest.raises(EntityNotFound):
        await uc.execute(request)


@pytest.mark.asyncio
async def test_settle_entry_not_found():
    entity = _make_entity()
    factoring = _make_factoring()
    position = _make_position(entity, factoring)
    uc, _ = _build_uc(entity, position)

    request = SettleManualInvestmentRequest(
        entity_id=entity.id,
        entry_id=uuid4(),
        product_type=ProductType.FACTORING,
    )

    with pytest.raises(ManualInvestmentNotFound):
        await uc.execute(request)


@pytest.mark.asyncio
async def test_settle_create_investment_tx_adds_money_in():
    entity = _make_entity()
    factoring = _make_factoring()
    position = _make_position(entity, factoring)
    uc, mocks = _build_uc(entity, position)

    request = SettleManualInvestmentRequest(
        entity_id=entity.id,
        entry_id=factoring.id,
        product_type=ProductType.FACTORING,
        interests=Dezimal("100"),
        create_investment_tx=True,
    )

    await uc.execute(request)

    saved = mocks["transaction_port"].save.await_args.args[0]
    investment = next(t for t in saved.investment if t.type == TxType.INVESTMENT)
    assert investment.amount == factoring.amount


@pytest.mark.asyncio
async def test_settle_no_investment_tx_by_default():
    entity = _make_entity()
    factoring = _make_factoring()
    position = _make_position(entity, factoring)
    uc, mocks = _build_uc(entity, position)

    request = SettleManualInvestmentRequest(
        entity_id=entity.id,
        entry_id=factoring.id,
        product_type=ProductType.FACTORING,
        interests=Dezimal("100"),
    )

    await uc.execute(request)

    saved = mocks["transaction_port"].save.await_args.args[0]
    assert not any(t.type == TxType.INVESTMENT for t in saved.investment)


@pytest.mark.asyncio
async def test_settle_recf_repays_pending_amount_not_original():
    entity = _make_entity()
    recf = _make_recf(pending="700")
    position = _make_recf_position(entity, recf)
    uc, mocks = _build_uc(entity, position)

    request = SettleManualInvestmentRequest(
        entity_id=entity.id,
        entry_id=recf.id,
        product_type=ProductType.REAL_ESTATE_CF,
        interests=Dezimal("0"),
    )

    await uc.execute(request)

    saved = mocks["transaction_port"].save.await_args.args[0]
    repayment = next(t for t in saved.investment if t.type == TxType.REPAYMENT)
    assert repayment.amount == Dezimal("700")


@pytest.mark.asyncio
async def test_settle_factoring_subtracts_prior_repayments():
    entity = _make_entity()
    factoring = _make_factoring()
    position = _make_position(entity, factoring)

    prior_repayment = make_investment_tx(
        entity,
        factoring,
        ProductType.FACTORING,
        TxType.REPAYMENT,
        Dezimal("400"),
        Dezimal(0),
        Dezimal(0),
        datetime.now(tzlocal()),
    )
    existing = MagicMock()
    existing.id = uuid4()
    existing.related_txs = [prior_repayment]

    historic_port = AsyncMock()
    historic_port.get_by_manual_key.return_value = existing

    uc, mocks = _build_uc(entity, position, historic_port=historic_port)

    request = SettleManualInvestmentRequest(
        entity_id=entity.id,
        entry_id=factoring.id,
        product_type=ProductType.FACTORING,
        interests=Dezimal("0"),
    )

    await uc.execute(request)

    saved = mocks["transaction_port"].save.await_args.args[0]
    repayment = next(t for t in saved.investment if t.type == TxType.REPAYMENT)
    assert repayment.amount == Dezimal("600")
