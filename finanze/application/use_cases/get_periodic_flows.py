from datetime import date, timedelta
from typing import Optional

from application.ports.periodic_flow_port import PeriodicFlowPort
from dateutil.relativedelta import relativedelta
from domain.earnings_expenses import FlowFrequency, PeriodicFlow
from domain.use_cases.get_periodic_flows import GetPeriodicFlows

frequency_delta_map = {
    FlowFrequency.MONTHLY: relativedelta(months=1),
    FlowFrequency.EVERY_TWO_MONTHS: relativedelta(months=2),
    FlowFrequency.QUARTERLY: relativedelta(months=3),
    FlowFrequency.EVERY_FOUR_MONTHS: relativedelta(months=4),
    FlowFrequency.SEMIANNUALLY: relativedelta(months=6),
    FlowFrequency.YEARLY: relativedelta(years=1),
}


def get_next_date(flow: PeriodicFlow) -> Optional[date]:
    if not flow.enabled:
        return None

    today = date.today()
    since_date = flow.since
    next_date = None

    if since_date > today:
        return since_date

    if flow.frequency == FlowFrequency.DAILY:
        next_date = today + timedelta(days=1)

    elif flow.frequency == FlowFrequency.WEEKLY:
        days_since = (today - since_date).days
        weeks_passed = days_since // 7
        next_date = since_date + timedelta(weeks=weeks_passed + 1)
        next_date = (
            next_date
            if next_date > today
            else since_date + timedelta(weeks=weeks_passed + 2)
        )

    elif flow.frequency in frequency_delta_map:
        delta = frequency_delta_map[flow.frequency]
        next_date = since_date
        while next_date <= today:
            next_date = next_date + delta

    if next_date and flow.until and next_date > flow.until:
        return None

    return next_date


class GetPeriodicFlowsImpl(GetPeriodicFlows):
    def __init__(self, periodic_flow_port: PeriodicFlowPort):
        self._periodic_flow_port = periodic_flow_port

    def execute(self) -> list[PeriodicFlow]:
        flows = self._periodic_flow_port.get_all()
        filled_flows = [
            PeriodicFlow(
                id=flow.id,
                name=flow.name,
                amount=flow.amount,
                currency=flow.currency,
                flow_type=flow.flow_type,
                frequency=flow.frequency,
                category=flow.category,
                enabled=flow.enabled,
                since=flow.since,
                until=flow.until,
                icon=flow.icon,
                linked=flow.linked,
                next_date=get_next_date(flow),
                max_amount=flow.max_amount,
            )
            for flow in flows
        ]
        return filled_flows
