from uuid import UUID

from domain.global_position import UpdatePositionRequest
from domain.use_cases.update_position import UpdatePosition
from flask import jsonify, request


async def update_position(update_position_uc: UpdatePosition):
    body = request.json
    if not isinstance(body, dict):
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Expected a JSON object"}
        ), 400

    try:
        entity_id = UUID(body["entity_id"])
        products = body.get("products", {})
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    req = UpdatePositionRequest(entity_id=entity_id, products=products)
    await update_position_uc.execute(req)
    return "", 204
