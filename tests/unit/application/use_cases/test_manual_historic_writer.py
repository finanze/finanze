from datetime import date, datetime
from unittest.mock import AsyncMock

import pytest
from dateutil.tz import tzlocal

from application.use_cases.manual_historic_common import ManualHistoricWriter
from domain.entity import Entity, EntityOrigin, EntityType
from domain.dezimal import Dezimal
from domain.fetch_record import DataSource
from domain.global_position import (
    FactoringDetail,
    FactoringInvestments,
    GlobalPosition,
    ProductType,
    RealEstateCFDetail,
    RealEstateCFInvestments,
)
from domain.historic import FactoringEntry, HistoricState
from domain.transactions import Transactions, TxType

from uuid import uuid4


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


def _make_position(entity, factoring):
    return GlobalPosition(
        id=uuid4(),
        entity=entity,
        products={ProductType.FACTORING: FactoringInvestments(entries=[factoring])},
    )


def _make_recf(pending):
    return RealEstateCFDetail(
        id=uuid4(),
        name="Project X",
        amount=Dezimal("1000"),
        pending_amount=pending,
        currency="EUR",
        interest_rate=Dezimal("0.1"),
        start=datetime(2024, 1, 1, tzinfo=tzlocal()),
        maturity=date(2024, 12, 31),
        type="SIMPLE",
        business_type="LENDING",
        state="OUTSTANDING",
        extended_maturity=None,
        extended_interest_rate=None,
        source=DataSource.MANUAL,
    )


def _make_recf_position(entity, recf):
    return GlobalPosition(
        id=uuid4(),
        entity=entity,
        products={ProductType.REAL_ESTATE_CF: RealEstateCFInvestments(entries=[recf])},
    )


@pytest.mark.asyncio
async def test_new_recf_with_lower_pending_creates_initial_repayment():
    historic_port = AsyncMock()
    historic_port.get_by_manual_key.return_value = None
    historic_port.get_manual_by_entity.return_value = []

    transaction_port = AsyncMock()
    transaction_port.get_by_entity_and_source.return_value = Transactions(
        investment=[], account=[]
    )
    registry = AsyncMock()

    writer = ManualHistoricWriter(
        historic_port,
        transaction_port=transaction_port,
        virtual_import_registry=registry,
    )

    entity = _make_entity()
    recf = _make_recf(Dezimal("700"))

    await writer.sync_position(entity, _make_recf_position(entity, recf))

    transaction_port.save.assert_awaited_once()
    saved_txs = transaction_port.save.await_args.args[0].investment
    assert len(saved_txs) == 2

    investment_tx = next(t for t in saved_txs if t.type == TxType.INVESTMENT)
    repayment_tx = next(t for t in saved_txs if t.type == TxType.REPAYMENT)
    assert investment_tx.amount == Dezimal("1000")
    assert repayment_tx.amount == Dezimal("300")

    saved_entry = historic_port.upsert.await_args.args[0]
    assert saved_entry.repaid == Dezimal("300")


@pytest.mark.asyncio
async def test_new_recf_full_pending_creates_only_investment():
    historic_port = AsyncMock()
    historic_port.get_by_manual_key.return_value = None
    historic_port.get_manual_by_entity.return_value = []

    transaction_port = AsyncMock()
    transaction_port.get_by_entity_and_source.return_value = Transactions(
        investment=[], account=[]
    )
    registry = AsyncMock()

    writer = ManualHistoricWriter(
        historic_port,
        transaction_port=transaction_port,
        virtual_import_registry=registry,
    )

    entity = _make_entity()
    recf = _make_recf(Dezimal("1000"))

    await writer.sync_position(entity, _make_recf_position(entity, recf))

    transaction_port.save.assert_awaited_once()
    saved_txs = transaction_port.save.await_args.args[0].investment
    assert len(saved_txs) == 1
    assert saved_txs[0].type == TxType.INVESTMENT
    assert saved_txs[0].amount == Dezimal("1000")


@pytest.mark.asyncio
async def test_new_recf_create_investment_txs_disabled_creates_none():
    historic_port = AsyncMock()
    historic_port.get_by_manual_key.return_value = None
    historic_port.get_manual_by_entity.return_value = []

    transaction_port = AsyncMock()
    registry = AsyncMock()

    writer = ManualHistoricWriter(
        historic_port,
        transaction_port=transaction_port,
        virtual_import_registry=registry,
    )

    entity = _make_entity()
    recf = _make_recf(Dezimal("700"))

    await writer.sync_position(
        entity,
        _make_recf_position(entity, recf),
        create_investment_txs=False,
    )

    transaction_port.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_upsert_ongoing_creates_manual_row():
    historic_port = AsyncMock()
    historic_port.get_by_manual_key.return_value = None
    historic_port.get_manual_by_entity.return_value = []
    writer = ManualHistoricWriter(historic_port)

    entity = _make_entity()
    factoring = _make_factoring()

    await writer.sync_position(entity, _make_position(entity, factoring))

    historic_port.upsert.assert_awaited_once()
    saved = historic_port.upsert.await_args.args[0]
    assert isinstance(saved, FactoringEntry)
    assert saved.source == DataSource.MANUAL
    assert saved.manual_key == ManualHistoricWriter.manual_key_for(entity.id, factoring)
    assert saved.invested == factoring.amount
    assert saved.related_txs == []


@pytest.mark.asyncio
async def test_upsert_ongoing_reuses_existing_id():
    entity = _make_entity()
    factoring = _make_factoring()
    manual_key = ManualHistoricWriter.manual_key_for(entity.id, factoring)

    existing = FactoringEntry(
        id=uuid4(),
        name=factoring.name,
        invested=factoring.amount,
        repaid=None,
        returned=None,
        currency="EUR",
        last_invest_date=factoring.start,
        last_tx_date=factoring.start,
        effective_maturity=None,
        net_return=None,
        fees=None,
        retentions=None,
        interests=None,
        state="OUTSTANDING",
        entity=entity,
        product_type=ProductType.FACTORING,
        related_txs=[],
        entity_account_id=None,
        source=DataSource.MANUAL,
        manual_key=manual_key,
        interest_rate=factoring.interest_rate,
        gross_interest_rate=factoring.interest_rate,
        maturity=factoring.maturity,
        type=factoring.type,
    )

    historic_port = AsyncMock()
    historic_port.get_by_manual_key.return_value = existing
    writer = ManualHistoricWriter(historic_port)

    result = await writer.upsert_ongoing(entity, factoring, ProductType.FACTORING)

    assert result.id == existing.id
    historic_port.upsert.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_ongoing_skips_finalized_row():
    entity = _make_entity()
    factoring = _make_factoring()
    manual_key = ManualHistoricWriter.manual_key_for(entity.id, factoring)

    finalized = FactoringEntry(
        id=uuid4(),
        name=factoring.name,
        invested=factoring.amount,
        repaid=factoring.amount,
        returned=factoring.amount,
        currency="EUR",
        last_invest_date=factoring.start,
        last_tx_date=factoring.start,
        effective_maturity=factoring.maturity,
        net_return=Dezimal("0"),
        fees=Dezimal("0"),
        retentions=Dezimal("0"),
        interests=Dezimal("0"),
        state=HistoricState.COMPLETED.value,
        entity=entity,
        product_type=ProductType.FACTORING,
        related_txs=[],
        entity_account_id=None,
        source=DataSource.MANUAL,
        manual_key=manual_key,
        interest_rate=factoring.interest_rate,
        gross_interest_rate=factoring.interest_rate,
        maturity=factoring.maturity,
        type=factoring.type,
    )

    historic_port = AsyncMock()
    historic_port.get_by_manual_key.return_value = finalized
    writer = ManualHistoricWriter(historic_port)

    result = await writer.upsert_ongoing(entity, factoring, ProductType.FACTORING)

    assert result is finalized
    historic_port.upsert.assert_not_awaited()


def test_manual_key_is_deterministic():
    entity = _make_entity()
    factoring = _make_factoring()
    k1 = ManualHistoricWriter.manual_key_for(entity.id, factoring)
    k2 = ManualHistoricWriter.manual_key_for(entity.id, factoring)
    assert k1 == k2


@pytest.mark.asyncio
async def test_sync_position_deletes_orphan_ongoing_row():
    entity = _make_entity()
    factoring = _make_factoring()

    orphan_id = uuid4()
    orphan = FactoringEntry(
        id=orphan_id,
        name="Old name",
        invested=factoring.amount,
        repaid=None,
        returned=None,
        currency="EUR",
        last_invest_date=factoring.start,
        last_tx_date=factoring.start,
        effective_maturity=None,
        net_return=None,
        fees=None,
        retentions=None,
        interests=None,
        state="OUTSTANDING",
        entity=entity,
        product_type=ProductType.FACTORING,
        related_txs=[],
        entity_account_id=None,
        source=DataSource.MANUAL,
        manual_key="stale-key-from-prev-identity",
        interest_rate=factoring.interest_rate,
        gross_interest_rate=factoring.interest_rate,
        maturity=factoring.maturity,
        type=factoring.type,
    )

    finalized = FactoringEntry(
        id=uuid4(),
        name="Settled",
        invested=factoring.amount,
        repaid=factoring.amount,
        returned=factoring.amount,
        currency="EUR",
        last_invest_date=factoring.start,
        last_tx_date=factoring.start,
        effective_maturity=factoring.maturity,
        net_return=Dezimal("0"),
        fees=Dezimal("0"),
        retentions=Dezimal("0"),
        interests=Dezimal("0"),
        state=HistoricState.COMPLETED.value,
        entity=entity,
        product_type=ProductType.FACTORING,
        related_txs=[],
        entity_account_id=None,
        source=DataSource.MANUAL,
        manual_key="another-stale-key",
        interest_rate=factoring.interest_rate,
        gross_interest_rate=factoring.interest_rate,
        maturity=factoring.maturity,
        type=factoring.type,
    )

    historic_port = AsyncMock()
    historic_port.get_by_manual_key.return_value = None
    historic_port.get_manual_by_entity.return_value = [orphan, finalized]
    writer = ManualHistoricWriter(historic_port)

    await writer.sync_position(entity, _make_position(entity, factoring))

    historic_port.delete_by_id.assert_awaited_once_with(orphan_id)
