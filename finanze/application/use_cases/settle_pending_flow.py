from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.pending_flow_port import PendingFlowPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.use_cases.manual_account_balance import ManualAccountBalanceUpdater
from domain.earnings_expenses import (
    FlowStatus,
    FlowType,
    SettlePendingFlowRequest,
)
from domain.exception.exceptions import FlowNotFound
from domain.use_cases.settle_pending_flow import SettlePendingFlow


class SettlePendingFlowImpl(SettlePendingFlow, AtomicUCMixin):
    def __init__(
        self,
        pending_flow_port: PendingFlowPort,
        balance_updater: ManualAccountBalanceUpdater,
        transaction_handler_port: TransactionHandlerPort,
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)
        self._pending_flow_port = pending_flow_port
        self._balance_updater = balance_updater

    async def execute(self, request: SettlePendingFlowRequest):
        flow = await self._pending_flow_port.get_by_id(request.flow_id)
        if flow is None:
            raise FlowNotFound()

        signed_amount = (
            flow.amount if flow.flow_type == FlowType.EARNING else -flow.amount
        )
        update = await self._balance_updater.prepare(
            account_id=request.account_id,
            amount=signed_amount,
            currency=flow.currency,
        )
        await self._balance_updater.write(update)

        flow.status = FlowStatus.COMPLETED
        flow.status_changed_at = update.date
        await self._pending_flow_port.update(flow)
