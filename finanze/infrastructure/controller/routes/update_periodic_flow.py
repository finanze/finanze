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

        flow = PeriodicFlow(
            id=UUID(body["id"]),
            name=body["name"],
            amount=Dezimal(body["amount"]),
            currency=body["currency"],
            flow_type=FlowType(body["flow_type"]),
            frequency=FlowFrequency(body["frequency"]),
            category=body.get("category"),
            enabled=body.get("enabled", True),
            since=since_date,
            until=until_date,
            icon=body.get("icon"),
            max_amount=Dezimal(body["max_amount"]) if body.get("max_amount") else None,
        )
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    await update_periodic_flow_uc.execute(flow)
    return "", 204
