import logging

from application.ports.connectable_integration import ConnectableIntegration
from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.oauth_connectable_integration import (
    OAuthConnectableIntegration,
)
from domain.exception.exceptions import (
    IntegrationNotFound,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
)
from domain.external_integration import (
    CompleteExternalIntegrationConnectionRequest,
    ExternalIntegrationId,
)
from domain.use_cases.complete_external_integration_connection import (
    CompleteExternalIntegrationConnection,
)


class CompleteExternalIntegrationConnectionImpl(CompleteExternalIntegrationConnection):
    def __init__(
        self,
        external_integration_port: ExternalIntegrationPort,
        integrations: dict[ExternalIntegrationId, ConnectableIntegration],
    ):
        self._external_integration_port = external_integration_port
        self._integrations = integrations

        self._log = logging.getLogger(__name__)

    async def execute(self, request: CompleteExternalIntegrationConnectionRequest):
        integration = self._integrations.get(request.integration_id)
        if not isinstance(integration, OAuthConnectableIntegration):
            raise IntegrationNotFound()

        try:
            payload = await integration.complete_authorization(request)
        except IntegrationSetupError as e:
            raise e
        except Exception as e:
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN) from e

        await self._external_integration_port.activate(request.integration_id, payload)
