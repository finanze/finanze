from datetime import date
from uuid import UUID

from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowStatus, FlowType, PendingFlow
from domain.exception.exceptions import FlowNotFound
from domain.use_cases.update_pending_flow import UpdatePendingFlow
from quart import jsonify, request


async def update_pending_flow(update_pending_flow_uc: UpdatePendingFlow):
    body = await request.get_json()

    try:
        flow_date = body.get("date") or None
        if flow_date and isinstance(flow_date, str):
            flow_date = date.fromisoformat(flow_date)

        flow = PendingFlow(
            id=UUID(body["id"]),
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

    try:
        await update_pending_flow_uc.execute(flow)
    except FlowNotFound:
        return jsonify({"code": "NOT_FOUND", "message": "Flow not found"}), 404

    return "", 204
