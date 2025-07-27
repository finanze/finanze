from domain.use_cases.get_periodic_flows import GetPeriodicFlows
from flask import jsonify


def get_periodic_flows(get_periodic_flows_uc: GetPeriodicFlows):
    flows = get_periodic_flows_uc.execute()
    return jsonify(
        [
            {
                "id": str(flow.id),
                "name": flow.name,
                "amount": str(flow.amount),
                "currency": flow.currency,
                "flow_type": flow.flow_type.value,
                "frequency": flow.frequency.value,
                "category": flow.category,
                "enabled": flow.enabled,
                "since": flow.since.isoformat() if flow.since else None,
                "until": flow.until.isoformat() if flow.until else None,
                "next_date": flow.next_date.isoformat() if flow.next_date else None,
            }
            for flow in flows
        ]
    ), 200
