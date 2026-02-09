from application.ports.pending_flow_port import PendingFlowPort
from domain.earnings_expenses import PendingFlow
from domain.use_cases.get_pending_flows import GetPendingFlows


class GetPendingFlowsImpl(GetPendingFlows):
    def __init__(self, pending_flow_port: PendingFlowPort):
        self._pending_flow_port = pending_flow_port

    async def execute(self) -> list[PendingFlow]:
        return await self._pending_flow_port.get_all()
