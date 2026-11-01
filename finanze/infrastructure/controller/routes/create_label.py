from domain.use_cases.create_label import CreateLabel
from infrastructure.controller.mappers.labeling_mapper import map_label
from quart import jsonify, request


async def create_label(create_label_uc: CreateLabel):
    body = await request.get_json()
    try:
        label = map_label(body)
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    created = await create_label_uc.execute(label)
    return jsonify(created), 201
