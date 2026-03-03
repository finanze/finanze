from uuid import UUID

from quart import request, jsonify

from domain.use_cases.add_entity_credentials import AddEntityCredentials


async def cancel_entity_login(add_entity_credentials: AddEntityCredentials):
    body = await request.get_json()
    entity = body.get("entity", None)
    if not entity:
        return jsonify({"message": "Entity not provided"}), 400

    add_entity_credentials.cancel_login(UUID(entity))
    return jsonify({"ok": True}), 200
