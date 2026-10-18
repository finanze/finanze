from typing import Annotated, Literal

from domain.external_integration import (
    ConnectedExternalIntegrationRequest,
    DisconnectedExternalIntegrationRequest,
    ExternalIntegrationId,
)
from pydantic import Field

from infrastructure.mcp.registry import ToolRegistry
from infrastructure.mcp.use_cases import McpUseCases

ManageableIntegration = Literal[
    "ETHERSCAN",
    "ETHPLORER",
    "ZERION",
    "COINGECKO",
    "COINMARKETCAP",
    "CRYPTOCOMPARE",
    "OPENROUTER",
    "OPENAI",
]


def register(registry: ToolRegistry, ucs: McpUseCases):
    @registry.read("List integrations")
    async def list_integrations():
        """List the external integrations (blockchain explorers, crypto price providers, AI providers, banking aggregators, Google Sheets) with their status and the payload fields required to connect them."""
        return await ucs.get_external_integrations.execute()

    @registry.write("Connect integration", idempotent=True, open_world=True)
    async def connect_integration(
        integration_id: ManageableIntegration,
        payload: Annotated[
            dict[str, str],
            Field(
                description='Fields required by the integration (see payload_schema in list_integrations), e.g. {"api_key": "..."}.'
            ),
        ],
    ):
        """Connect or update an external integration with its credentials. Credentials sent here pass through the AI client, so suggest the user enters them in the Finanze app instead if they prefer."""
        await ucs.connect_external_integration.execute(
            ConnectedExternalIntegrationRequest(
                integration_id=ExternalIntegrationId(integration_id), payload=payload
            )
        )
        return {"connected": integration_id}

    @registry.write("Disconnect integration", destructive=True, idempotent=True)
    async def disconnect_integration(integration_id: ManageableIntegration):
        """Disconnect an external integration, deleting its stored credentials."""
        await ucs.disconnect_external_integration.execute(
            DisconnectedExternalIntegrationRequest(
                integration_id=ExternalIntegrationId(integration_id)
            )
        )
        return {"disconnected": integration_id}
