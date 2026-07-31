from uuid import UUID

from quart import jsonify, request


async def market_forecast_closed_positions(get_market_forecast_closed_positions_uc):
    entity_account_ids: list[UUID] = []
    for value in request.args.getlist("entity_account_id"):
        try:
            entity_account_ids.append(UUID(value))
        except ValueError:
            return jsonify({"error": "Invalid entity_account_id format"}), 400

    result = await get_market_forecast_closed_positions_uc.execute(
        entity_account_ids or None,
    )
    return jsonify(result), 200
