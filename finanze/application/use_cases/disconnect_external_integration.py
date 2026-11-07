import logging

from application.ports.connectable_integration import ConnectableIntegration
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
    def __init__(
        self,
        external_integration_port: ExternalIntegrationPort,
        integrations: dict[ExternalIntegrationId, ConnectableIntegration],
    ):
        self._external_integration_port = external_integration_port
        self._integrations = integrations
        self._log = logging.getLogger(__name__)

    async def execute(self, request: DisconnectedExternalIntegrationRequest):
        try:
            integration_id = ExternalIntegrationId(request.integration_id)
        except ValueError:
            raise IntegrationNotFound()

        integration = self._integrations.get(integration_id)
        connectable = isinstance(integration, ConnectableIntegration)
        payload = (
            await self._external_integration_port.get_payload(
                integration_id, include_expired=True
            )
            if connectable
            else None
        )

        await self._external_integration_port.deactivate(integration_id)

        if not connectable:
            return
        try:
            await integration.teardown(payload)
        except Exception:
            self._log.warning(
                f"Could not tear down integration {integration_id.value}",
                exc_info=True,
            )
