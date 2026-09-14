from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from dateutil.tz import tzlocal

from application.use_cases.add_manual_transaction import AddManualTransactionImpl
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.exception.exceptions import EntityNotFound
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.transactions import (
    AddManualTransactionRequest,
    FundTx,
    Transactions,
    TxType,
)


class _NoopTransaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *args):
        return False


def _make_transaction_handler():
    handler = MagicMock()
    handler.start = MagicMock(return_value=_NoopTransaction())
    return handler


def _make_entity(entity_id=None, name="Test Entity"):
    return Entity(
        id=entity_id or uuid4(),
        name=name,
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )


def _make_fund_tx(entity, name="Buy Fund", tx_type=TxType.BUY):
    return FundTx(
        id=None,
        ref="TX-FUND",
        name=name,
        amount=Dezimal("5000"),
        currency="EUR",
        type=tx_type,
        date=datetime(2025, 3, 1, 12, tzinfo=tzlocal()),
        entity=entity,
        source=DataSource.MANUAL,
        product_type=ProductType.FUND,
        isin="LU0000000001",
        shares=Dezimal("50"),
        price=Dezimal("100"),
        fees=Dezimal("10"),
    )


def _build_uc(entity_port=None):
    if entity_port is None:
        entity_port = AsyncMock()
    transaction_port = AsyncMock()
    virtual_import_registry = AsyncMock()
    virtual_import_registry.get_last_import_records.return_value = []
    historic_port = AsyncMock()
    uc = AddManualTransactionImpl(
        entity_port=entity_port,
        transaction_port=transaction_port,
        virtual_import_registry=virtual_import_registry,
        transaction_handler_port=_make_transaction_handler(),
        historic_port=historic_port,
    )
    return uc, {
        "entity_port": entity_port,
        "transaction_port": transaction_port,
        "historic_port": historic_port,
    }


@pytest.mark.asyncio
async def test_execute_saves_two_investment_txs():
    entity = _make_entity()
    entity_port = AsyncMock()
    entity_port.get_by_id.return_value = entity
    uc, mocks = _build_uc(entity_port)

    request = AddManualTransactionRequest(
        txs=[
            _make_fund_tx(entity, name="Origin", tx_type=TxType.TRANSFER_OUT),
            _make_fund_tx(entity, name="Dest", tx_type=TxType.TRANSFER_IN),
        ]
    )
    result_id = await uc.execute(request)

    mocks["transaction_port"].save.assert_awaited_once()
    saved = mocks["transaction_port"].save.await_args[0][0]
    assert isinstance(saved, Transactions)
    assert len(saved.investment) == 2
    assert saved.investment[0].name == "Origin"
    assert saved.investment[1].name == "Dest"
    assert saved.investment[0].id is not None
    assert saved.investment[0].id == result_id
    mocks["historic_port"].link_txs.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_empty_raises():
    uc, mocks = _build_uc()
    with pytest.raises(ValueError, match="At least one transaction is required"):
        await uc.execute(AddManualTransactionRequest(txs=[]))
    mocks["transaction_port"].save.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_missing_second_entity_saves_nothing():
    entity = _make_entity()
    missing_id = uuid4()

    async def get_by_id(entity_id):
        if entity_id == entity.id:
            return entity
        return None

    entity_port = AsyncMock()
    entity_port.get_by_id = AsyncMock(side_effect=get_by_id)
    uc, mocks = _build_uc(entity_port)
    dest_entity = _make_entity(entity_id=missing_id, name="Missing")

    with pytest.raises(EntityNotFound):
        await uc.execute(
            AddManualTransactionRequest(
                txs=[
                    _make_fund_tx(entity, name="Origin", tx_type=TxType.TRANSFER_OUT),
                    _make_fund_tx(dest_entity, name="Dest", tx_type=TxType.TRANSFER_IN),
                ]
            )
        )
    mocks["transaction_port"].save.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_links_historic_entry():
    entity = _make_entity()
    entity_port = AsyncMock()
    entity_port.get_by_id.return_value = entity
    uc, mocks = _build_uc(entity_port)
    historic_id = uuid4()

    await uc.execute(
        AddManualTransactionRequest(
            txs=[_make_fund_tx(entity)],
            historic_entry_id=historic_id,
        )
    )

    mocks["historic_port"].link_txs.assert_awaited_once()
    linked_id, tx_ids = mocks["historic_port"].link_txs.await_args[0]
    assert linked_id == historic_id
    assert len(tx_ids) == 1
    assert isinstance(tx_ids[0], UUID)
