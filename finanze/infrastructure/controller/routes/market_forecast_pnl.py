from uuid import UUID

from quart import jsonify, request

_ALLOWED_INTERVALS = {"1d", "1w", "1m", "all"}


async def market_forecast_pnl(get_market_forecast_pnl_uc):
    entity_account_ids: list[UUID] = []
    for value in request.args.getlist("entity_account_id"):
        try:
            entity_account_ids.append(UUID(value))
        except ValueError:
            return jsonify({"error": "Invalid entity_account_id format"}), 400

    interval = request.args.get("interval", "all")
    if interval not in _ALLOWED_INTERVALS:
        return jsonify({"error": "Invalid interval"}), 400

    result = await get_market_forecast_pnl_uc.execute(
        entity_account_ids or None,
        interval,
    )
    return jsonify(result), 200
