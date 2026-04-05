from application.ports.periodic_flow_port import PeriodicFlowPort
from domain.earnings_expenses import PeriodicFlow
from domain.use_cases.update_periodic_flow import UpdatePeriodicFlow


class UpdatePeriodicFlowImpl(UpdatePeriodicFlow):
    def __init__(self, periodic_flow_port: PeriodicFlowPort):
        self._periodic_flow_port = periodic_flow_port

    async def execute(self, flow: PeriodicFlow):
        existing = await self._periodic_flow_port.get_by_id(flow.id)
        if (
            existing
            and existing.real_estate_flow
            and existing.real_estate_flow.flow_subtype == "LOAN"
        ):
            flow.amount = existing.amount
            flow.currency = existing.currency
            flow.flow_type = existing.flow_type
            flow.frequency = existing.frequency
            flow.category = existing.category
            flow.enabled = existing.enabled
            flow.since = existing.since
            flow.until = existing.until
            flow.linked = existing.linked
            flow.real_estate_flow = existing.real_estate_flow
        await self._periodic_flow_port.update(flow)
