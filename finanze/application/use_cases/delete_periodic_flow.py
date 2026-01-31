from uuid import UUID

from application.ports.periodic_flow_port import PeriodicFlowPort
from domain.use_cases.delete_periodic_flow import DeletePeriodicFlow


class DeletePeriodicFlowImpl(DeletePeriodicFlow):
    def __init__(self, periodic_flow_port: PeriodicFlowPort):
        self._periodic_flow_port = periodic_flow_port

    async def execute(self, flow_id: UUID):
        await self._periodic_flow_port.delete(flow_id)
