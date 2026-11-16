from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from dateutil.tz import tzlocal

from application.use_cases.add_manual_transaction import AddManualTransactionImpl
from application.use_cases.manual_account_balance import ManualAccountBalanceUpdater
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.exception.exceptions import EntityNotFound, ManualAccountNotFound
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.labeling import LabelingTrigger
from domain.transactions import (
    AccountTx,
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


def _build_uc(entity_port=None, balance_updater=None):
    if entity_port is None:
        entity_port = AsyncMock()
    if balance_updater is None:
        balance_updater = AsyncMock(spec=ManualAccountBalanceUpdater)
    transaction_port = AsyncMock()
    virtual_import_registry = AsyncMock()
    virtual_import_registry.get_last_import_records.return_value = []
    historic_port = AsyncMock()
    transaction_labeler = AsyncMock()
    uc = AddManualTransactionImpl(
        entity_port=entity_port,
        transaction_port=transaction_port,
        virtual_import_registry=virtual_import_registry,
        transaction_handler_port=_make_transaction_handler(),
        historic_port=historic_port,
        label_port=AsyncMock(),
        transaction_label_port=AsyncMock(),
        transaction_labeler=transaction_labeler,
        balance_updater=balance_updater,
    )
    return uc, {
        "entity_port": entity_port,
        "transaction_port": transaction_port,
        "historic_port": historic_port,
        "transaction_labeler": transaction_labeler,
        "balance_updater": balance_updater,
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


def _make_account_tx(entity):
    return AccountTx(
        id=None,
        ref="TX-ACC",
        name="Groceries",
        amount=Dezimal("25"),
        currency="EUR",
        type=TxType.OUTFLOW,
        date=datetime(2025, 3, 1, 12, tzinfo=tzlocal()),
        entity=entity,
        source=DataSource.MANUAL,
        product_type=ProductType.ACCOUNT,
        fees=Dezimal("0"),
        retentions=Dezimal("0"),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "external_labeling, expected_trigger",
    [(None, LabelingTrigger.AUTO), (True, LabelingTrigger.MANUAL)],
)
async def test_execute_account_tx_external_labeling_trigger(
    external_labeling, expected_trigger
):
    entity = _make_entity()
    entity_port = AsyncMock()
    entity_port.get_by_id.return_value = entity
    uc, mocks = _build_uc(entity_port)

    result_id = await uc.execute(
        AddManualTransactionRequest(
            txs=[_make_account_tx(entity)], external_labeling=external_labeling
        )
    )

    labeler = mocks["transaction_labeler"]
    labeler.classify.assert_awaited_once()
    labeler.classify_external.assert_awaited_once()
    selection, trigger = labeler.classify_external.await_args[0]
    assert selection.ids == [result_id]
    assert trigger == expected_trigger


@pytest.mark.asyncio
async def test_execute_account_tx_external_labeling_disabled_skips_external():
    entity = _make_entity()
    entity_port = AsyncMock()
    entity_port.get_by_id.return_value = entity
    uc, mocks = _build_uc(entity_port)

    await uc.execute(
        AddManualTransactionRequest(
            txs=[_make_account_tx(entity)], external_labeling=False
        )
    )

    labeler = mocks["transaction_labeler"]
    labeler.classify.assert_awaited_once()
    labeler.classify_external.assert_not_awaited()
    mocks["balance_updater"].prepare.assert_not_awaited()
    mocks["balance_updater"].write.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tx_type, amount, fees, retentions, expected_delta",
    [
        (TxType.INFLOW, "100", "2.50", "0", Dezimal("97.50")),
        (TxType.INTEREST, "50", "1", "9", Dezimal("40")),
        (TxType.OUTFLOW, "100", "2", "0", Dezimal("-102")),
        (TxType.FEE, "15", "15", "0", Dezimal("-15")),
    ],
)
async def test_execute_updates_manual_account_balance(
    tx_type, amount, fees, retentions, expected_delta
):
    entity = _make_entity()
    entity_port = AsyncMock()
    entity_port.get_by_id.return_value = entity
    uc, mocks = _build_uc(entity_port)
    prepared = MagicMock()
    mocks["balance_updater"].prepare.return_value = prepared
    account_id = uuid4()

    tx = AccountTx(
        id=None,
        ref="TX-BAL",
        name="Movement",
        amount=Dezimal(amount),
        currency="EUR",
        type=tx_type,
        date=datetime(2025, 3, 1, 12, tzinfo=tzlocal()),
        entity=entity,
        source=DataSource.MANUAL,
        product_type=ProductType.ACCOUNT,
        fees=Dezimal(fees),
        retentions=Dezimal(retentions),
    )

    await uc.execute(
        AddManualTransactionRequest(
            txs=[tx],
            balance_account_id=account_id,
            external_labeling=False,
        )
    )

    mocks["balance_updater"].prepare.assert_awaited_once_with(
        account_id=account_id,
        amount=expected_delta,
        currency="EUR",
        entity_id=entity.id,
    )
    mocks["balance_updater"].write.assert_awaited_once_with(prepared)
    mocks["transaction_port"].save.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_balance_update_rejects_non_account_tx():
    entity = _make_entity()
    entity_port = AsyncMock()
    entity_port.get_by_id.return_value = entity
    uc, mocks = _build_uc(entity_port)

    with pytest.raises(ValueError, match="only supported for ACCOUNT"):
        await uc.execute(
            AddManualTransactionRequest(
                txs=[_make_fund_tx(entity)],
                balance_account_id=uuid4(),
            )
        )

    mocks["transaction_port"].save.assert_not_awaited()
    mocks["balance_updater"].prepare.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_balance_update_rejects_multiple_txs():
    entity = _make_entity()
    entity_port = AsyncMock()
    entity_port.get_by_id.return_value = entity
    uc, mocks = _build_uc(entity_port)

    with pytest.raises(ValueError, match="single transaction"):
        await uc.execute(
            AddManualTransactionRequest(
                txs=[_make_account_tx(entity), _make_account_tx(entity)],
                balance_account_id=uuid4(),
            )
        )

    mocks["transaction_port"].save.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_balance_update_rejects_non_positive_amount():
    entity = _make_entity()
    entity_port = AsyncMock()
    entity_port.get_by_id.return_value = entity
    uc, mocks = _build_uc(entity_port)
    tx = _make_account_tx(entity)
    tx.amount = Dezimal(0)

    with pytest.raises(ValueError, match="positive transaction amount"):
        await uc.execute(
            AddManualTransactionRequest(
                txs=[tx],
                balance_account_id=uuid4(),
            )
        )

    mocks["transaction_port"].save.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_balance_update_account_not_found_saves_nothing():
    entity = _make_entity()
    entity_port = AsyncMock()
    entity_port.get_by_id.return_value = entity
    uc, mocks = _build_uc(entity_port)
    account_id = uuid4()
    mocks["balance_updater"].prepare.side_effect = ManualAccountNotFound(account_id)

    with pytest.raises(ManualAccountNotFound):
        await uc.execute(
            AddManualTransactionRequest(
                txs=[_make_account_tx(entity)],
                balance_account_id=account_id,
            )
        )

    mocks["transaction_port"].save.assert_not_awaited()
    mocks["balance_updater"].write.assert_not_awaited()
