from application.ports.external_integration_port import ExternalIntegrationPort
from domain.external_integration import (
    EXTERNAL_INTEGRATION_PAYLOAD_SCHEMAS,
    AvailableExternalIntegrations,
)
from domain.use_cases.get_external_integrations import GetExternalIntegrations


class GetExternalIntegrationsImpl(GetExternalIntegrations):
    def __init__(self, external_integration_port: ExternalIntegrationPort):
        self._external_integration_port = external_integration_port

    async def execute(self) -> AvailableExternalIntegrations:
        integrations = await self._external_integration_port.get_all()

        for integration in integrations:
            integration.payload_schema = EXTERNAL_INTEGRATION_PAYLOAD_SCHEMAS[
                integration.id
            ]

        return AvailableExternalIntegrations(integrations)
