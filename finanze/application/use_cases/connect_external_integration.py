import logging

from application.ports.connectable_integration import ConnectableIntegration
from application.ports.external_integration_port import ExternalIntegrationPort
from domain.exception.exceptions import (
    IntegrationNotFound,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
)
from domain.external_integration import (
    EXTERNAL_INTEGRATION_PAYLOAD_SCHEMAS,
    ConnectedExternalIntegrationRequest,
    ExternalIntegrationId,
)
from domain.use_cases.connect_external_integration import ConnectExternalIntegration


class ConnectExternalIntegrationImpl(ConnectExternalIntegration):
    def __init__(
        self,
        external_integration_port: ExternalIntegrationPort,
        integrations: dict[ExternalIntegrationId, ConnectableIntegration],
    ):
        self._external_integration_port = external_integration_port
        self._integrations = integrations

        self._log = logging.getLogger(__name__)

    async def execute(self, request: ConnectedExternalIntegrationRequest):
        integration = self._integrations.get(request.integration_id)
        if integration is None:
            raise IntegrationNotFound()

        payload = request.payload
        payload_schema = EXTERNAL_INTEGRATION_PAYLOAD_SCHEMAS[request.integration_id]

        for key, value in payload_schema.items():
            if key not in payload:
                raise IntegrationSetupError(
                    IntegrationSetupErrorCode.INVALID_CREDENTIALS
                )

        try:
            await integration.setup(payload)
        except IntegrationSetupError as e:
            raise e
        except Exception as e:
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN) from e

        await self._external_integration_port.activate(request.integration_id, payload)
