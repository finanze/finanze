from application.ports.periodic_flow_port import PeriodicFlowPort
from domain.earnings_expenses import PeriodicFlow
from domain.use_cases.update_periodic_flow import UpdatePeriodicFlow


class UpdatePeriodicFlowImpl(UpdatePeriodicFlow):
    def __init__(self, periodic_flow_port: PeriodicFlowPort):
        self._periodic_flow_port = periodic_flow_port

    def execute(self, flow: PeriodicFlow):
        self._periodic_flow_port.update(flow)
