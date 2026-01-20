from domain.external_integration import (
    DisconnectedExternalIntegrationRequest,
    ExternalIntegrationId,
)
from domain.use_cases.disconnect_external_integration import (
    DisconnectExternalIntegration,
)
from quart import jsonify


async def disconnect_external_integration(
    disconnect_external_integrations_uc: DisconnectExternalIntegration,
    integration_id: str,
):
    try:
        external_integration_id = ExternalIntegrationId(integration_id)
    except ValueError:
        return (
            jsonify({"message": f"Error: invalid integration '{integration_id}'"}),
            400,
        )

    req = DisconnectedExternalIntegrationRequest(external_integration_id)
    await disconnect_external_integrations_uc.execute(req)

    return "", 204
