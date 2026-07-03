from uuid import UUID

from application.ports.pending_flow_port import PendingFlowPort
from domain.use_cases.delete_pending_flow import DeletePendingFlow


class DeletePendingFlowImpl(DeletePendingFlow):
    def __init__(self, pending_flow_port: PendingFlowPort):
        self._pending_flow_port = pending_flow_port

    async def execute(self, flow_id: UUID):
        await self._pending_flow_port.delete(flow_id)
