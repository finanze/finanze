from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from application.ports.exchange_rate_provider import ExchangeRateProvider
from application.ports.pending_flow_port import PendingFlowPort
from application.ports.position_port import PositionPort
from application.use_cases.manual_position_snapshot import (
    ManualPositionSnapshotWriter,
)
from application.use_cases.settle_pending_flow import SettlePendingFlowImpl
from domain.dezimal import Dezimal
from domain.earnings_expenses import (
    FlowStatus,
    FlowType,
    PendingFlow,
    SettlePendingFlowRequest,
)
from domain.entity import Entity, EntityOrigin, EntityType
from domain.exception.exceptions import FlowNotFound, ManualAccountNotFound
from domain.fetch_record import DataSource
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    GlobalPosition,
    ProductType,
)


class _NoopTransaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *args):
        return None


def _make_transaction_handler():
    handler = MagicMock()
    handler.start = MagicMock(return_value=_NoopTransaction())
    return handler


def _make_entity(id=None):
    return Entity(
        id=id or uuid4(),
        name="TestBank",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )


def _make_account(id=None, total=Dezimal(1000), currency="EUR"):
    return Account(
        id=id or uuid4(),
        total=total,
        currency=currency,
        type=AccountType.CHECKING,
        name="Main",
        iban="ES0000000000000000001234",
        source=DataSource.MANUAL,
    )


def _make_position(entity=None, accounts=None) -> GlobalPosition:
    return GlobalPosition(
        id=uuid4(),
        entity=entity or _make_entity(),
        products={ProductType.ACCOUNT: Accounts(entries=accounts or [])},
    )


def _make_flow(amount=Dezimal(100), flow_type=FlowType.EARNING, currency="EUR"):
    return PendingFlow(
        id=uuid4(),
        name="Salary",
        amount=amount,
        currency=currency,
        flow_type=flow_type,
        category=None,
        status=FlowStatus.ACTIVE,
        date=None,
        icon=None,
    )


def _build_use_case():
    pending_flow_port = AsyncMock(spec=PendingFlowPort)
    position_port = AsyncMock(spec=PositionPort)
    snapshot_writer = AsyncMock(spec=ManualPositionSnapshotWriter)
    exchange_rate_provider = AsyncMock(spec=ExchangeRateProvider)
    transaction_handler = _make_transaction_handler()

    uc = SettlePendingFlowImpl(
        pending_flow_port=pending_flow_port,
        position_port=position_port,
        snapshot_writer=snapshot_writer,
        exchange_rate_provider=exchange_rate_provider,
        transaction_handler_port=transaction_handler,
    )
    return (
        uc,
        pending_flow_port,
        position_port,
        snapshot_writer,
        exchange_rate_provider,
    )


class TestSettlePendingFlow:
    @pytest.mark.asyncio
    async def test_flow_not_found_raises(self):
        uc, pending_flow_port, position_port, snapshot_writer, _ = _build_use_case()
        pending_flow_port.get_by_id.return_value = None

        with pytest.raises(FlowNotFound):
            await uc.execute(
                SettlePendingFlowRequest(flow_id=uuid4(), account_id=uuid4())
            )

        snapshot_writer.write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_account_not_found_raises(self):
        uc, pending_flow_port, position_port, snapshot_writer, _ = _build_use_case()
        pending_flow_port.get_by_id.return_value = _make_flow()
        position_port.get_last_grouped_by_entity.return_value = {}

        with pytest.raises(ManualAccountNotFound):
            await uc.execute(
                SettlePendingFlowRequest(flow_id=uuid4(), account_id=uuid4())
            )

        snapshot_writer.write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_earning_adds_to_balance(self):
        uc, pending_flow_port, position_port, snapshot_writer, _ = _build_use_case()
        entity = _make_entity()
        account = _make_account(total=Dezimal(1000))
        position = _make_position(entity=entity, accounts=[account])
        flow = _make_flow(amount=Dezimal(250), flow_type=FlowType.EARNING)

        pending_flow_port.get_by_id.return_value = flow
        position_port.get_last_grouped_by_entity.return_value = {entity: position}

        await uc.execute(
            SettlePendingFlowRequest(flow_id=flow.id, account_id=account.id)
        )

        assert account.total == Dezimal(1250)
        assert position.source == DataSource.MANUAL
        snapshot_writer.write.assert_awaited_once()
        written_entity, written_position = snapshot_writer.write.await_args[0]
        assert written_entity is entity
        assert written_position is position
        assert flow.status == FlowStatus.COMPLETED
        pending_flow_port.update.assert_awaited_once_with(flow)
        query = position_port.get_last_grouped_by_entity.await_args[0][0]
        assert query.real is False

    @pytest.mark.asyncio
    async def test_expense_subtracts_from_balance(self):
        uc, pending_flow_port, position_port, snapshot_writer, _ = _build_use_case()
        entity = _make_entity()
        account = _make_account(total=Dezimal(1000))
        position = _make_position(entity=entity, accounts=[account])
        flow = _make_flow(amount=Dezimal(250), flow_type=FlowType.EXPENSE)

        pending_flow_port.get_by_id.return_value = flow
        position_port.get_last_grouped_by_entity.return_value = {entity: position}

        await uc.execute(
            SettlePendingFlowRequest(flow_id=flow.id, account_id=account.id)
        )

        assert account.total == Dezimal(750)
        snapshot_writer.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cross_currency_converts(self):
        uc, pending_flow_port, position_port, snapshot_writer, provider = (
            _build_use_case()
        )
        entity = _make_entity()
        account = _make_account(total=Dezimal(1000), currency="EUR")
        position = _make_position(entity=entity, accounts=[account])
        flow = _make_flow(
            amount=Dezimal(110), flow_type=FlowType.EARNING, currency="USD"
        )

        pending_flow_port.get_by_id.return_value = flow
        position_port.get_last_grouped_by_entity.return_value = {entity: position}
        provider.get_matrix.return_value = {"EUR": {"USD": Dezimal("1.1")}}

        await uc.execute(
            SettlePendingFlowRequest(flow_id=flow.id, account_id=account.id)
        )

        assert account.total == Dezimal(1100)
        provider.get_matrix.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_non_manual_account_skipped(self):
        uc, pending_flow_port, position_port, snapshot_writer, _ = _build_use_case()
        entity = _make_entity()
        account = _make_account()
        account.source = DataSource.REAL
        position = _make_position(entity=entity, accounts=[account])

        pending_flow_port.get_by_id.return_value = _make_flow()
        position_port.get_last_grouped_by_entity.return_value = {entity: position}

        with pytest.raises(ManualAccountNotFound):
            await uc.execute(
                SettlePendingFlowRequest(flow_id=uuid4(), account_id=account.id)
            )
