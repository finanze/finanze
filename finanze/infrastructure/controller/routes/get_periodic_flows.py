from domain.use_cases.get_periodic_flows import GetPeriodicFlows
from quart import jsonify


async def get_periodic_flows(get_periodic_flows_uc: GetPeriodicFlows):
    flows = await get_periodic_flows_uc.execute()
    return jsonify(
        [
            {
                "id": str(flow.id),
                "name": flow.name,
                "amount": flow.amount,
                "currency": flow.currency,
                "flow_type": flow.flow_type.value,
                "frequency": flow.frequency.value,
                "category": flow.category,
                "enabled": flow.enabled,
                "since": flow.since.isoformat() if flow.since else None,
                "until": flow.until.isoformat() if flow.until else None,
                "linked": flow.linked,
                "next_date": flow.next_date.isoformat() if flow.next_date else None,
                "max_amount": flow.max_amount,
                "icon": flow.icon,
            }
            for flow in flows
        ]
    ), 200
