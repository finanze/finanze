import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from dateutil.tz import tzlocal

from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.exchange_rate_provider import ExchangeRateProvider
from application.ports.pending_flow_port import PendingFlowPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.use_cases.manual_position_snapshot import (
    ManualPositionSnapshotWriter,
)
from domain.dezimal import Dezimal
from domain.earnings_expenses import (
    FlowStatus,
    FlowType,
    SettlePendingFlowRequest,
)
from domain.entity import Entity
from domain.exception.exceptions import (
    FlowNotFound,
    ManualAccountNotFound,
)
from domain.exchange_rate import ExchangeRates
from domain.fetch_record import DataSource
from domain.global_position import (
    Account,
    GlobalPosition,
    PositionQueryRequest,
    ProductType,
)
from domain.use_cases.settle_pending_flow import SettlePendingFlow


class SettlePendingFlowImpl(SettlePendingFlow, AtomicUCMixin):
    def __init__(
        self,
        pending_flow_port: PendingFlowPort,
        position_port: PositionPort,
        snapshot_writer: ManualPositionSnapshotWriter,
        exchange_rate_provider: ExchangeRateProvider,
        transaction_handler_port: TransactionHandlerPort,
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)
        self._pending_flow_port = pending_flow_port
        self._position_port = position_port
        self._snapshot_writer = snapshot_writer
        self._exchange_rate_provider = exchange_rate_provider

        self._log = logging.getLogger(__name__)

    async def execute(self, request: SettlePendingFlowRequest):
        flow = await self._pending_flow_port.get_by_id(request.flow_id)
        if flow is None:
            raise FlowNotFound()

        located = await self._locate_account(request.account_id)
        if located is None:
            raise ManualAccountNotFound(request.account_id)

        entity, position, account = located

        signed_amount = (
            flow.amount if flow.flow_type == FlowType.EARNING else -flow.amount
        )
        converted = await self._convert(signed_amount, flow.currency, account.currency)
        account.total = account.total + converted

        now = datetime.now(tzlocal())
        position.id = uuid4()
        position.date = now
        position.source = DataSource.MANUAL

        await self._snapshot_writer.write(entity, position)

        flow.status = FlowStatus.COMPLETED
        flow.status_changed_at = now
        await self._pending_flow_port.update(flow)

    async def _locate_account(
        self, account_id
    ) -> Optional[tuple[Entity, GlobalPosition, Account]]:
        positions = await self._position_port.get_last_grouped_by_entity(
            PositionQueryRequest(real=False)
        )
        for entity, position in positions.items():
            container = position.products.get(ProductType.ACCOUNT)
            if not (container and getattr(container, "entries", None)):
                continue
            for account in container.entries:
                if account.id == account_id and account.source == DataSource.MANUAL:
                    return entity, position, account
        return None

    async def _convert(
        self, amount: Dezimal, source_currency: str, target_currency: str
    ) -> Dezimal:
        if source_currency == target_currency:
            return amount
        matrix: ExchangeRates = await self._exchange_rate_provider.get_matrix()
        try:
            rate = matrix[target_currency][source_currency]
        except KeyError:
            raise ValueError(
                f"Missing exchange rate {source_currency}->{target_currency}"
            )
        if rate == 0:
            raise ValueError(
                f"Invalid exchange rate {source_currency}->{target_currency}"
            )
        return amount / rate
