from domain.external_integration import (
    CompleteExternalIntegrationConnectionRequest,
    ExternalIntegrationId,
)
from domain.use_cases.complete_external_integration_connection import (
    CompleteExternalIntegrationConnection,
)
from quart import jsonify, request


async def complete_external_integration_connection(
    complete_external_integration_connection_uc: CompleteExternalIntegrationConnection,
    integration_id: str,
):
    body = await request.get_json(silent=True) or {}

    try:
        external_integration_id = ExternalIntegrationId(integration_id)
    except ValueError:
        return (
            jsonify({"message": f"Error: invalid integration '{integration_id}'"}),
            400,
        )

    state = body.get("state")
    if not isinstance(state, str) or not state:
        return jsonify({"message": "Error: missing state"}), 400

    code = body.get("code")
    error = body.get("error")
    if (code is not None and not isinstance(code, str)) or (
        error is not None and not isinstance(error, str)
    ):
        return jsonify({"message": "Error: invalid callback parameters"}), 400

    req = CompleteExternalIntegrationConnectionRequest(
        integration_id=external_integration_id,
        state=state,
        code=code or None,
        error=error or None,
    )
    await complete_external_integration_connection_uc.execute(req)

    return "", 204
