from unittest.mock import AsyncMock

import pytest
from application.ports.ai_client import AIClient
from application.ports.external_integration_port import ExternalIntegrationPort
from application.use_cases.get_ai_server_info import GetAIServerInfoImpl
from domain.ai import AIClientFeature, AIServerInfo, AIServerKind
from domain.exception.exceptions import (
    ExternalIntegrationRequired,
    IntegrationNotFound,
)
from domain.external_integration import ExternalIntegrationId

CREDENTIALS = {"base_url": "http://localhost:11434"}
INFO = AIServerInfo(
    url="http://localhost:11434/v1",
    api_key_set=False,
    reachable=True,
    kind=AIServerKind.OLLAMA,
)


class FakeAIClient(AIClient):
    def __init__(self, features: set[AIClientFeature]):
        self._features = features
        self.credentials = None

    async def setup(self, payload):
        pass

    def features(self):
        return self._features

    async def get_model(self, model_id, credentials):
        return None

    async def generate(self, request, credentials):
        raise NotImplementedError

    async def get_server_info(self, credentials):
        self.credentials = credentials
        return INFO


def _use_case(client: AIClient, credentials=CREDENTIALS) -> GetAIServerInfoImpl:
    port = AsyncMock(spec=ExternalIntegrationPort)
    port.get_payload = AsyncMock(return_value=credentials)
    return GetAIServerInfoImpl(port, {ExternalIntegrationId.OPENAI_COMPATIBLE: client})


class TestGetAIServerInfo:
    @pytest.mark.asyncio
    async def test_returns_client_server_info(self):
        client = FakeAIClient({AIClientFeature.SERVER_INFO})
        result = await _use_case(client).execute("OPENAI_COMPATIBLE")
        assert result == INFO
        assert client.credentials == CREDENTIALS

    @pytest.mark.parametrize("provider_id", ["NOPE", "OPENAI"])
    @pytest.mark.asyncio
    async def test_unknown_or_unregistered_provider(self, provider_id):
        client = FakeAIClient({AIClientFeature.SERVER_INFO})
        with pytest.raises(IntegrationNotFound):
            await _use_case(client).execute(provider_id)

    @pytest.mark.asyncio
    async def test_provider_without_server_info(self):
        client = FakeAIClient({AIClientFeature.GENERATION})
        with pytest.raises(IntegrationNotFound):
            await _use_case(client).execute("OPENAI_COMPATIBLE")

    @pytest.mark.asyncio
    async def test_requires_connected_integration(self):
        client = FakeAIClient({AIClientFeature.SERVER_INFO})
        with pytest.raises(ExternalIntegrationRequired):
            await _use_case(client, credentials=None).execute("OPENAI_COMPATIBLE")
        assert client.credentials is None
