from datetime import date

from domain.money_event import MoneyEventQuery
from domain.use_cases.get_money_events import GetMoneyEvents
from quart import jsonify, request


async def get_money_events(get_money_events_uc: GetMoneyEvents):
    from_date_param = request.args.get("from_date")
    to_date_param = request.args.get("to_date")

    if not all([from_date_param, to_date_param]):
        return jsonify({"error": "from_date and to_date are required"}), 400

    try:
        from_date = date.fromisoformat(from_date_param)
        to_date = date.fromisoformat(to_date_param)
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    if from_date > to_date:
        return jsonify({"error": "from_date must be before or equal to to_date"}), 400

    query = MoneyEventQuery(
        from_date=from_date,
        to_date=to_date,
    )

    result = await get_money_events_uc.execute(query)

    events_payload = []
    for event in result.events:
        details = None
        if event.details:
            details = {
                "target_type": event.details.target_type.value,
                "target_subtype": event.details.target_subtype.value
                if event.details.target_subtype
                else None,
                "target": event.details.target,
                "target_name": event.details.target_name,
            }
        events_payload.append(
            {
                "id": str(event.id),
                "name": event.name,
                "amount": event.amount,
                "currency": event.currency,
                "date": event.date.isoformat(),
                "type": event.type.value,
                "frequency": event.frequency.value if event.frequency else None,
                "icon": event.icon,
                "details": details,
                "product_type": event.product_type.value
                if event.product_type
                else None,
            }
        )

    return (
        jsonify(
            {
                "events": events_payload,
            }
        ),
        200,
    )
