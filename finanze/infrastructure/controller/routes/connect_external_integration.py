from domain.external_integration import (
    ConnectedExternalIntegrationRequest,
    ExternalIntegrationId,
)
from domain.use_cases.connect_external_integration import ConnectExternalIntegration
from flask import jsonify, request


def connect_external_integration(
    connect_external_integrations_uc: ConnectExternalIntegration,
    integration_id: str,
):
    body = request.json

    try:
        external_integration_id = ExternalIntegrationId(integration_id)
    except ValueError:
        return (
            jsonify({"message": f"Error: invalid integration '{integration_id}'"}),
            400,
        )

    payload = body.get("payload")
    if not payload:
        return jsonify({"message": "Error: missing payload"}), 400

    req = ConnectedExternalIntegrationRequest(external_integration_id, payload)
    connect_external_integrations_uc.execute(req)

    return "", 204
