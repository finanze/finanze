from application.ports.label_port import LabelPort
from application.ports.periodic_flow_port import PeriodicFlowPort
from domain.earnings_expenses import PeriodicFlow
from domain.exception.exceptions import InvalidBudgetLabel, LabelNotFound
from domain.labeling import LabelCategory
from domain.use_cases.save_periodic_flow import SavePeriodicFlow


class SavePeriodicFlowImpl(SavePeriodicFlow):
    def __init__(self, periodic_flow_port: PeriodicFlowPort, label_port: LabelPort):
        self._periodic_flow_port = periodic_flow_port
        self._label_port = label_port

    async def execute(self, flow: PeriodicFlow):
        if flow.label_id is not None:
            label = await self._label_port.get_by_id(flow.label_id)
            if label is None:
                raise LabelNotFound()
            if label.category == LabelCategory.EXCLUDED:
                raise InvalidBudgetLabel()
        await self._periodic_flow_port.save(flow)
