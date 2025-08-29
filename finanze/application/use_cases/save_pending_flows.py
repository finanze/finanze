from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.pending_flow_port import PendingFlowPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from domain.earnings_expenses import PendingFlow
from domain.use_cases.save_pending_flows import SavePendingFlows


class SavePendingFlowsImpl(SavePendingFlows, AtomicUCMixin):
    def __init__(
        self,
        pending_flow_port: PendingFlowPort,
        transaction_handler_port: TransactionHandlerPort,
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)

        self._pending_flow_port = pending_flow_port

    async def execute(self, flows: list[PendingFlow]):
        self._pending_flow_port.delete_all()
        self._pending_flow_port.save(flows)
