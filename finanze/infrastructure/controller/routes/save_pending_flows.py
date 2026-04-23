from datetime import date

from domain.earnings_expenses import PendingFlow, FlowType
from domain.use_cases.save_pending_flows import SavePendingFlows
from domain.dezimal import Dezimal
from quart import jsonify, request


async def save_pending_flows(save_pending_flows_uc: SavePendingFlows):
    body = await request.get_json()

    flows = []
    try:
        for flow_data in body.get("flows", []):
            flow_date = flow_data.get("date") or None
            if flow_date and isinstance(flow_date, str):
                flow_date = date.fromisoformat(flow_date)

            flow = PendingFlow(
                id=None,
                name=flow_data["name"],
                amount=Dezimal(flow_data["amount"]),
                currency=flow_data["currency"],
                flow_type=FlowType(flow_data["flow_type"]),
                category=flow_data.get("category"),
                enabled=flow_data.get("enabled", True),
                date=flow_date,
                icon=flow_data.get("icon"),
            )
            flows.append(flow)
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    await save_pending_flows_uc.execute(flows)
    return "", 204
