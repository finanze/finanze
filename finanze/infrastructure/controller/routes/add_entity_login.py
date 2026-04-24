from uuid import UUID

from quart import request, jsonify

from domain.entity_login import TwoFactor, EntityLoginRequest
from domain.use_cases.add_entity_credentials import AddEntityCredentials


async def add_entity_login(add_entity_credentials: AddEntityCredentials):
    body = await request.get_json()
    entity = body.get("entity", None)
    if not entity:
        return jsonify({"message": "Source entity not provided"}), 400

    entity = UUID(entity)

    credentials = body.get("credentials", None)
    if not credentials:
        return jsonify({"message": "Credentials not provided"}), 400

    code = body.get("code", None)
    process_id = body.get("processId", None)
    token = body.get("token", None)
    entity_account_id = body.get("entityAccountId", None)
    account_name = body.get("accountName", None)

    login_request = EntityLoginRequest(
        entity_id=entity,
        credentials=credentials,
        two_factor=TwoFactor(code=code, process_id=process_id, token=token),
        entity_account_id=UUID(entity_account_id) if entity_account_id else None,
        account_name=account_name,
    )
    result = await add_entity_credentials.execute(login_request)

    response = {"code": result.code}
    if result.message:
        response["message"] = result.message
    if result.details:
        details = dict(result.details)
        if "challenge_domain" in details:
            details["challengeDomain"] = details.pop("challenge_domain")
        response["details"] = details
    if result.confirmation_type:
        response["confirmationType"] = result.confirmation_type
    if result.process_id:
        response["processId"] = result.process_id
    if result.challenge_type:
        response["challengeType"] = result.challenge_type
    if result.entity_account_id:
        response["entityAccountId"] = str(result.entity_account_id)
    return jsonify(response), 200
