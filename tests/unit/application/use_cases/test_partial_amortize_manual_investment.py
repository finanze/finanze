from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from application.use_cases.partial_amortize_manual_investment import (
    PartialAmortizeManualInvestmentImpl,
)
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType, Feature
from domain.exception.exceptions import ManualInvestmentNotFound
from domain.global_position import (
    FactoringDetail,
    FactoringInvestments,
    GlobalPosition,
    ProductType,
    RealEstateCFDetail,
    RealEstateCFInvestments,
)
from domain.historic import PartialAmortizeManualInvestmentRequest
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


def _make_factoring():
    return FactoringDetail(
        id=uuid4(),
        name="Loan A",
        amount=Dezimal("1000"),
        currency="EUR",
        interest_rate=Dezimal("0.1"),
        start=datetime(2024, 1, 1, tzinfo=tzlocal()),
        maturity=date(2024, 12, 31),
        type="SIMPLE",
        state="OUTSTANDING",
    )


def _make_recf():
    return RealEstateCFDetail(
        id=uuid4(),
        name="Project X",
        amount=Dezimal("1000"),
        pending_amount=Dezimal("1000"),
        currency="EUR",
        interest_rate=Dezimal("0.1"),
        start=datetime(2024, 1, 1, tzinfo=tzlocal()),
        maturity=date(2024, 12, 31),
        type="LOAN",
        state="OUTSTANDING",
    )


def _make_position(entity, product_type, entry):
    container = (
        FactoringInvestments(entries=[entry])
        if product_type == ProductType.FACTORING
        else RealEstateCFInvestments(entries=[entry])
    )
    return GlobalPosition(
        id=uuid4(),
        entity=entity,
        products={product_type: container},
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


def _build_uc(entity, position):
    entity_port = AsyncMock()
    entity_port.get_by_id.return_value = entity

    position_port = AsyncMock()
    position_port.get_by_id.return_value = position

    transaction_port = AsyncMock()
    transaction_port.get_by_entity_and_source.return_value = Transactions(
        investment=[], account=[]
    )

    historic_port = AsyncMock()
    historic_port.get_by_manual_key.return_value = None

    registry = _make_registry(entity, position)
    snapshot_writer = AsyncMock()

    uc = PartialAmortizeManualInvestmentImpl(
        entity_port=entity_port,
        position_port=position_port,
        transaction_port=transaction_port,
        historic_port=historic_port,
        virtual_import_registry=registry,
        snapshot_writer=snapshot_writer,
        transaction_handler_port=_make_transaction_handler(),
    )
    return uc, {
        "transaction_port": transaction_port,
        "historic_port": historic_port,
        "snapshot_writer": snapshot_writer,
    }


@pytest.mark.asyncio
async def test_amortize_recf_reduces_pending_and_creates_repayment():
    entity = _make_entity()
    recf = _make_recf()
    position = _make_position(entity, ProductType.REAL_ESTATE_CF, recf)
    uc, mocks = _build_uc(entity, position)

    request = PartialAmortizeManualInvestmentRequest(
        entity_id=entity.id,
        entry_id=recf.id,
        product_type=ProductType.REAL_ESTATE_CF,
        amount=Dezimal("300"),
    )

    await uc.execute(request)

    saved = mocks["transaction_port"].save.await_args.args[0]
    repayment = next(t for t in saved.investment if t.type == TxType.REPAYMENT)
    assert repayment.amount == Dezimal("300")

    mocks["snapshot_writer"].write.assert_awaited_once()
    written = mocks["snapshot_writer"].write.await_args.args[1]
    updated = written.products[ProductType.REAL_ESTATE_CF].entries[0]
    assert updated.pending_amount == Dezimal("700")


@pytest.mark.asyncio
async def test_amortize_recf_pending_floored_at_zero():
    entity = _make_entity()
    recf = _make_recf()
    position = _make_position(entity, ProductType.REAL_ESTATE_CF, recf)
    uc, mocks = _build_uc(entity, position)

    request = PartialAmortizeManualInvestmentRequest(
        entity_id=entity.id,
        entry_id=recf.id,
        product_type=ProductType.REAL_ESTATE_CF,
        amount=Dezimal("1500"),
    )

    await uc.execute(request)

    written = mocks["snapshot_writer"].write.await_args.args[1]
    updated = written.products[ProductType.REAL_ESTATE_CF].entries[0]
    assert updated.pending_amount == Dezimal("0")


@pytest.mark.asyncio
async def test_amortize_factoring_no_snapshot_rewrite():
    entity = _make_entity()
    factoring = _make_factoring()
    position = _make_position(entity, ProductType.FACTORING, factoring)
    uc, mocks = _build_uc(entity, position)

    request = PartialAmortizeManualInvestmentRequest(
        entity_id=entity.id,
        entry_id=factoring.id,
        product_type=ProductType.FACTORING,
        amount=Dezimal("300"),
    )

    await uc.execute(request)

    mocks["snapshot_writer"].write.assert_not_awaited()


@pytest.mark.asyncio
async def test_amortize_keeps_historic_ongoing():
    entity = _make_entity()
    recf = _make_recf()
    position = _make_position(entity, ProductType.REAL_ESTATE_CF, recf)
    uc, mocks = _build_uc(entity, position)

    request = PartialAmortizeManualInvestmentRequest(
        entity_id=entity.id,
        entry_id=recf.id,
        product_type=ProductType.REAL_ESTATE_CF,
        amount=Dezimal("300"),
    )

    await uc.execute(request)

    mocks["historic_port"].upsert.assert_awaited_once()
    ongoing = mocks["historic_port"].upsert.await_args.args[0]
    assert ongoing.effective_maturity is None
    assert ongoing.state == recf.state


@pytest.mark.asyncio
async def test_amortize_with_interests_creates_interest_tx():
    entity = _make_entity()
    recf = _make_recf()
    position = _make_position(entity, ProductType.REAL_ESTATE_CF, recf)
    uc, mocks = _build_uc(entity, position)

    request = PartialAmortizeManualInvestmentRequest(
        entity_id=entity.id,
        entry_id=recf.id,
        product_type=ProductType.REAL_ESTATE_CF,
        amount=Dezimal("300"),
        interests=Dezimal("50"),
        fees=Dezimal("2"),
        retentions=Dezimal("10"),
    )

    await uc.execute(request)

    saved = mocks["transaction_port"].save.await_args.args[0]
    interest = next(t for t in saved.investment if t.type == TxType.INTEREST)
    assert interest.amount == Dezimal("50")
    assert interest.fees == Dezimal("2")
    assert interest.retentions == Dezimal("10")


@pytest.mark.asyncio
async def test_amortize_entry_not_found():
    entity = _make_entity()
    recf = _make_recf()
    position = _make_position(entity, ProductType.REAL_ESTATE_CF, recf)
    uc, _ = _build_uc(entity, position)

    request = PartialAmortizeManualInvestmentRequest(
        entity_id=entity.id,
        entry_id=uuid4(),
        product_type=ProductType.REAL_ESTATE_CF,
        amount=Dezimal("300"),
    )

    with pytest.raises(ManualInvestmentNotFound):
        await uc.execute(request)


@pytest.mark.asyncio
async def test_amortize_create_investment_tx_adds_money_in():
    entity = _make_entity()
    recf = _make_recf()
    position = _make_position(entity, ProductType.REAL_ESTATE_CF, recf)
    uc, mocks = _build_uc(entity, position)

    request = PartialAmortizeManualInvestmentRequest(
        entity_id=entity.id,
        entry_id=recf.id,
        product_type=ProductType.REAL_ESTATE_CF,
        amount=Dezimal("300"),
        create_investment_tx=True,
    )

    await uc.execute(request)

    saved = mocks["transaction_port"].save.await_args.args[0]
    investment = next(t for t in saved.investment if t.type == TxType.INVESTMENT)
    assert investment.amount == recf.amount


@pytest.mark.asyncio
async def test_amortize_no_investment_tx_by_default():
    entity = _make_entity()
    recf = _make_recf()
    position = _make_position(entity, ProductType.REAL_ESTATE_CF, recf)
    uc, mocks = _build_uc(entity, position)

    request = PartialAmortizeManualInvestmentRequest(
        entity_id=entity.id,
        entry_id=recf.id,
        product_type=ProductType.REAL_ESTATE_CF,
        amount=Dezimal("300"),
    )

    await uc.execute(request)

    saved = mocks["transaction_port"].save.await_args.args[0]
    assert not any(t.type == TxType.INVESTMENT for t in saved.investment)
