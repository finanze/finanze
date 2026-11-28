from application.ports.connectable_integration import ConnectableIntegration
from application.ports.external_integration_port import ExternalIntegrationPort
from domain.external_integration import (
    AI_PROVIDER_FAMILIES,
    AI_PROVIDER_FAMILY_NAMES,
    AI_PROVIDER_PLATFORMS,
    EXTERNAL_INTEGRATION_OPTIONAL_FIELDS,
    EXTERNAL_INTEGRATION_PAYLOAD_SCHEMAS,
    AvailableExternalIntegrations,
    ExternalIntegrationId,
    ExternalIntegrationFamily,
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
            family_id = AI_PROVIDER_FAMILIES.get(integration.id)
            integration.family = (
                ExternalIntegrationFamily(
                    id=family_id.value, name=AI_PROVIDER_FAMILY_NAMES[family_id]
                )
                if family_id
                else None
            )
            platforms = AI_PROVIDER_PLATFORMS.get(integration.id)
            integration.platforms = list(platforms) if platforms else None
            integration.payload_schema = EXTERNAL_INTEGRATION_PAYLOAD_SCHEMAS[
                integration.id
            ]
            optional_fields = EXTERNAL_INTEGRATION_OPTIONAL_FIELDS.get(integration.id)
            if optional_fields:
                integration.optional_fields = sorted(optional_fields)

        return AvailableExternalIntegrations(integrations)
