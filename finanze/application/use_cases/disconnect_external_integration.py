import logging

from application.ports.external_integration_port import ExternalIntegrationPort
from domain.exception.exceptions import IntegrationNotFound
from domain.external_integration import (
    DisconnectedExternalIntegrationRequest,
    ExternalIntegrationId,
)
from domain.use_cases.disconnect_external_integration import (
    DisconnectExternalIntegration,
)


class DisconnectExternalIntegrationImpl(DisconnectExternalIntegration):
    def __init__(self, external_integration_port: ExternalIntegrationPort):
        self._external_integration_port = external_integration_port
        self._log = logging.getLogger(__name__)

    async def execute(self, request: DisconnectedExternalIntegrationRequest):
        try:
            _ = ExternalIntegrationId(request.integration_id)
        except ValueError:
            raise IntegrationNotFound()

        await self._external_integration_port.deactivate(request.integration_id)
