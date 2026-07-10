from datetime import date

from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowStatus, FlowType, PendingFlow
from domain.use_cases.save_pending_flow import SavePendingFlow
from quart import jsonify, request


async def save_pending_flow(save_pending_flow_uc: SavePendingFlow):
    body = await request.get_json()

    try:
        flow_date = body.get("date") or None
        if flow_date and isinstance(flow_date, str):
            flow_date = date.fromisoformat(flow_date)

        flow = PendingFlow(
            id=None,
            name=body["name"],
            amount=Dezimal(body["amount"]),
            currency=body["currency"],
            flow_type=FlowType(body["flow_type"]),
            category=body.get("category") or None,
            status=FlowStatus(body.get("status", FlowStatus.ACTIVE.value)),
            date=flow_date,
            icon=body.get("icon"),
        )
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    await save_pending_flow_uc.execute(flow)
    return "", 201
