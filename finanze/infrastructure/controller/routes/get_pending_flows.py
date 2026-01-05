from domain.use_cases.get_pending_flows import GetPendingFlows
from quart import jsonify


async def get_pending_flows(get_pending_flows_uc: GetPendingFlows):
    flows = await get_pending_flows_uc.execute()
    return jsonify(
        [
            {
                "id": str(flow.id),
                "name": flow.name,
                "amount": flow.amount,
                "currency": flow.currency,
                "flow_type": flow.flow_type.value,
                "category": flow.category,
                "enabled": flow.enabled,
                "date": flow.date.isoformat() if flow.date else None,
                "icon": flow.icon,
            }
            for flow in flows
        ]
    ), 200
