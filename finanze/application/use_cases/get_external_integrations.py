from application.ports.connectable_integration import ConnectableIntegration
from application.ports.external_integration_port import ExternalIntegrationPort
from domain.external_integration import (
    EXTERNAL_INTEGRATION_PAYLOAD_SCHEMAS,
    AvailableExternalIntegrations,
    ExternalIntegrationId,
)
from domain.use_cases.get_external_integrations import GetExternalIntegrations


class GetExternalIntegrationsImpl(GetExternalIntegrations):
    def __init__(
        self,
        external_integration_port: ExternalIntegrationPort,
        integrations: dict[ExternalIntegrationId, ConnectableIntegration],
    ):
        self._external_integration_port = external_integration_port
        self._integrations = integrations

    async def execute(self) -> AvailableExternalIntegrations:
        integrations = await self._external_integration_port.get_all()

        for integration in integrations:
            integration.available = integration.id in self._integrations
            integration.payload_schema = EXTERNAL_INTEGRATION_PAYLOAD_SCHEMAS[
                integration.id
            ]

        return AvailableExternalIntegrations(integrations)
