from uuid import UUID

from flask import request, jsonify

from domain.entity_login import TwoFactor, EntityLoginRequest
from domain.use_cases.add_entity_credentials import AddEntityCredentials


async def add_entity_login(add_entity_credentials: AddEntityCredentials):
    body = request.json
    entity = body.get("entity", None)
    if not entity:
        return jsonify({"message": "Source entity not provided"}), 400

    entity = UUID(entity)

    credentials = body.get("credentials", None)
    if not credentials:
        return jsonify({"message": "Credentials not provided"}), 400

    code = body.get("code", None)
    process_id = body.get("processId", None)

    login_request = EntityLoginRequest(
        entity_id=entity,
        credentials=credentials,
        two_factor=TwoFactor(code=code, process_id=process_id)
    )
    result = await add_entity_credentials.execute(login_request)

    response = {"code": result.code}
    if result.message:
        response["message"] = result.message
    if result.details:
        response["details"] = result.details
    if result.process_id:
        response["processId"] = result.process_id
    return jsonify(response), 200
