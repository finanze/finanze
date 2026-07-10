from datetime import date

from domain.networth_timeline import NetworthTimelineQuery
from domain.use_cases.get_networth_timeline import GetNetworthTimeline
from quart import jsonify, request


async def networth_timeline(get_networth_timeline_uc: GetNetworthTimeline):
    base_currency = request.args.get("base_currency")
    from_date_param = request.args.get("from_date")
    to_date_param = request.args.get("to_date")
    no_calculation = request.args.get("no_calculation", "false").lower() in (
        "true",
        "1",
        "yes",
    )

    if not base_currency:
        return jsonify(
            {
                "code": "INVALID_REQUEST",
                "message": "base_currency is required.",
            }
        ), 400

    from_date = None
    to_date = None
    try:
        if from_date_param:
            from_date = date.fromisoformat(from_date_param)
        if to_date_param:
            to_date = date.fromisoformat(to_date_param)
    except ValueError:
        return jsonify(
            {
                "code": "INVALID_REQUEST",
                "message": "Invalid date format. Use YYYY-MM-DD.",
            }
        ), 400

    if from_date and to_date and from_date > to_date:
        return jsonify(
            {
                "code": "INVALID_REQUEST",
                "message": "from_date must be before or equal to to_date",
            }
        ), 400

    query = NetworthTimelineQuery(
        base_currency=base_currency,
        from_date=from_date,
        to_date=to_date,
        no_calculation=no_calculation,
    )

    result = await get_networth_timeline_uc.execute(query)

    payload = {
        "currency": result.currency,
        "points": [
            {
                "date": point.date.isoformat(),
                "total": point.total,
                "breakdown": dict(point.breakdown),
            }
            for point in result.points
        ],
    }
    return jsonify(payload), 200
