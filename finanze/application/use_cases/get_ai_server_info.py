from application.ports.ai_client import AIClient
from application.ports.external_integration_port import ExternalIntegrationPort
from domain.ai import AIClientFeature, AIServerInfo
from domain.exception.exceptions import (
    ExternalIntegrationRequired,
    IntegrationNotFound,
)
from domain.external_integration import ExternalIntegrationId
from domain.use_cases.get_ai_server_info import GetAIServerInfo


class GetAIServerInfoImpl(GetAIServerInfo):
    def __init__(
        self,
        external_integration_port: ExternalIntegrationPort,
        clients: dict[ExternalIntegrationId, AIClient],
    ):
        self._external_integration_port = external_integration_port
        self._clients = clients

    async def execute(self, provider_id: str) -> AIServerInfo:
        try:
            integration_id = ExternalIntegrationId(provider_id)
        except ValueError:
            raise IntegrationNotFound()
        client = self._clients.get(integration_id)
        if client is None or AIClientFeature.SERVER_INFO not in client.features():
            raise IntegrationNotFound()

        credentials = await self._external_integration_port.get_payload(integration_id)
        if credentials is None:
            raise ExternalIntegrationRequired([integration_id])

        return await client.get_server_info(credentials)
