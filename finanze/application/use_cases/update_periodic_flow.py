from application.ports.label_port import LabelPort
from application.ports.periodic_flow_port import PeriodicFlowPort
from domain.earnings_expenses import PeriodicFlow
from domain.exception.exceptions import InvalidBudgetLabel, LabelNotFound
from domain.labeling import LabelCategory
from domain.use_cases.update_periodic_flow import UpdatePeriodicFlow


class UpdatePeriodicFlowImpl(UpdatePeriodicFlow):
    def __init__(self, periodic_flow_port: PeriodicFlowPort, label_port: LabelPort):
        self._periodic_flow_port = periodic_flow_port
        self._label_port = label_port

    async def execute(self, flow: PeriodicFlow, *, label_id_provided: bool = True):
        existing = await self._periodic_flow_port.get_by_id(flow.id)
        if not label_id_provided and existing:
            flow.label_id = existing.label_id
        elif flow.label_id is not None:
            label = await self._label_port.get_by_id(flow.label_id)
            if label is None:
                raise LabelNotFound()
            if label.category == LabelCategory.EXCLUDED:
                raise InvalidBudgetLabel()
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
