from datetime import datetime

from application.ports.pending_flow_port import PendingFlowPort
from dateutil.tz import tzlocal
from domain.earnings_expenses import PendingFlow
from domain.exception.exceptions import FlowNotFound
from domain.use_cases.update_pending_flow import UpdatePendingFlow


class UpdatePendingFlowImpl(UpdatePendingFlow):
    def __init__(self, pending_flow_port: PendingFlowPort):
        self._pending_flow_port = pending_flow_port

    async def execute(self, flow: PendingFlow):
        existing = await self._pending_flow_port.get_by_id(flow.id)
        if existing is None:
            raise FlowNotFound()

        if existing.status != flow.status:
            flow.status_changed_at = datetime.now(tzlocal())
        else:
            flow.status_changed_at = existing.status_changed_at

        await self._pending_flow_port.update(flow)
