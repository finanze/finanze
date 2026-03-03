from uuid import UUID

from quart import request, jsonify

from domain.use_cases.cancel_entity_login import CancelEntityLogin


async def cancel_entity_login(cancel_entity_login_uc: CancelEntityLogin):
    body = await request.get_json()
    entity = body.get("entity", None)
    if not entity:
        return jsonify({"message": "Entity not provided"}), 400

    cancel_entity_login_uc.execute(UUID(entity))
    return jsonify({"ok": True}), 200
