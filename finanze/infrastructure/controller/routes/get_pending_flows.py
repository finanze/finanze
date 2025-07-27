from domain.use_cases.get_pending_flows import GetPendingFlows
from flask import jsonify


def get_pending_flows(get_pending_flows_uc: GetPendingFlows):
    flows = get_pending_flows_uc.execute()
    return jsonify(
        [
            {
                "id": str(flow.id),
                "name": flow.name,
                "amount": str(flow.amount),
                "currency": flow.currency,
                "flow_type": flow.flow_type.value,
                "category": flow.category,
                "enabled": flow.enabled,
                "date": flow.date.isoformat() if flow.date else None,
            }
            for flow in flows
        ]
    ), 200
