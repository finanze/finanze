from datetime import date
from uuid import UUID

from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowFrequency, FlowType, PeriodicFlow
from domain.use_cases.update_periodic_flow import UpdatePeriodicFlow
from quart import jsonify, request


async def update_periodic_flow(update_periodic_flow_uc: UpdatePeriodicFlow):
    body = await request.get_json()

    try:
        since_date = body["since"]
        if isinstance(since_date, str):
            since_date = date.fromisoformat(since_date)

        until_date = body.get("until") or None
        if until_date and isinstance(until_date, str):
            until_date = date.fromisoformat(until_date)

        label_id = body.get("label_id")
        if label_id is not None and not isinstance(label_id, str):
            raise TypeError("label_id must be a UUID string or null")

        flow = PeriodicFlow(
            id=UUID(body["id"]),
            name=body["name"],
            amount=Dezimal(body["amount"]),
            currency=body["currency"],
            flow_type=FlowType(body["flow_type"]),
            frequency=FlowFrequency(body["frequency"]),
            category=body.get("category") or None,
            enabled=body.get("enabled", True),
            since=since_date,
            until=until_date,
            icon=body.get("icon"),
            max_amount=Dezimal(body["max_amount"]) if body.get("max_amount") else None,
            label_id=UUID(label_id) if label_id is not None else None,
        )
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    await update_periodic_flow_uc.execute(flow, label_id_provided="label_id" in body)
    return "", 204
