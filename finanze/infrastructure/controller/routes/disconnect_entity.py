from uuid import UUID

from quart import request, jsonify

from domain.entity_login import EntityDisconnectRequest
from domain.use_cases.disconnect_entity import DisconnectEntity


async def disconnect_entity(disconnect_entity_uc: DisconnectEntity):
    body = await request.get_json()
    entity_account_id_str = body.get("entityAccountId")
    if not entity_account_id_str:
        return jsonify({"message": "Entity account id not provided"}), 400

    try:
        entity_account_id = UUID(entity_account_id_str)
    except Exception:
        return jsonify({"message": "Invalid UUID"}), 400

    req = EntityDisconnectRequest(entity_account_id=entity_account_id)
    await disconnect_entity_uc.execute(req)

    return "", 204
