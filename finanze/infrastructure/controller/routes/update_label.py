from uuid import UUID

from domain.use_cases.update_label import UpdateLabel
from infrastructure.controller.mappers.labeling_mapper import map_label
from quart import jsonify, request


async def update_label(update_label_uc: UpdateLabel, label_id: str):
    body = await request.get_json()
    try:
        label = map_label(body, UUID(label_id))
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    await update_label_uc.execute(label)
    return "", 204
