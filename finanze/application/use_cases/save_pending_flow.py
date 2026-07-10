from datetime import datetime

from application.ports.pending_flow_port import PendingFlowPort
from dateutil.tz import tzlocal
from domain.earnings_expenses import PendingFlow
from domain.use_cases.save_pending_flow import SavePendingFlow


class SavePendingFlowImpl(SavePendingFlow):
    def __init__(self, pending_flow_port: PendingFlowPort):
        self._pending_flow_port = pending_flow_port

    async def execute(self, flow: PendingFlow):
        if flow.status_changed_at is None:
            flow.status_changed_at = datetime.now(tzlocal())
        await self._pending_flow_port.save(flow)
