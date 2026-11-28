from domain.external_integration import (
    ExternalIntegrationConnectionStatus,
    ExternalIntegrationId,
    PollExternalIntegrationConnectionRequest,
)
from domain.use_cases.poll_external_integration_connection import (
    PollExternalIntegrationConnection,
)
from quart import jsonify, request


async def poll_external_integration_connection(
    poll_external_integration_connection_uc: PollExternalIntegrationConnection,
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

    flow_id = body.get("flow_id")
    if not isinstance(flow_id, str) or not flow_id:
        return jsonify({"message": "Error: missing flow_id"}), 400

    result = await poll_external_integration_connection_uc.execute(
        PollExternalIntegrationConnectionRequest(external_integration_id, flow_id)
    )

    response = {"status": result.status.value}
    if result.status == ExternalIntegrationConnectionStatus.PENDING:
        response["interval"] = result.interval
    return jsonify(response), 200
