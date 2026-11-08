import ast
from dataclasses import asdict
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from application.ports.connectable_integration import ConnectableIntegration
from application.use_cases.connect_external_integration import (
    ConnectExternalIntegrationImpl,
)
from application.use_cases.disconnect_external_integration import (
    DisconnectExternalIntegrationImpl,
)
from application.use_cases.get_external_integrations import (
    GetExternalIntegrationsImpl,
)
from domain.exception.exceptions import (
    IntegrationSetupError,
    IntegrationSetupErrorCode,
)
from domain.external_integration import (
    AI_PROVIDER_PLATFORMS,
    AIProviderFamily,
    ConnectedExternalIntegrationRequest,
    DisconnectedExternalIntegrationRequest,
    ExternalIntegration,
    ExternalIntegrationId,
    ExternalIntegrationStatus,
    ExternalIntegrationType,
)
from domain.platform import IntegrationPlatform


class FakeIntegration(ConnectableIntegration):
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.payloads = []
        self.teardowns = 0

    async def setup(self, payload):
        self.payloads.append(payload)

    async def teardown(self, payload=None):
        self.teardowns += 1
        if self.error:
            raise self.error


def _connect(integration_id, payload, integration=None):
    port = AsyncMock()
    integration = integration or FakeIntegration()
    use_case = ConnectExternalIntegrationImpl(port, {integration_id: integration})
    return (
        use_case.execute(ConnectedExternalIntegrationRequest(integration_id, payload)),
        port,
        integration,
    )


class TestConnectOptionalFields:
    @pytest.mark.asyncio
    async def test_local_models_without_fields(self):
        call, port, integration = _connect(ExternalIntegrationId.LOCAL_MODELS, {})
        await call
        assert integration.payloads == [{}]
        port.activate.assert_awaited_once_with(ExternalIntegrationId.LOCAL_MODELS, {})

    @pytest.mark.asyncio
    async def test_blank_optional_fields_are_dropped(self):
        call, port, integration = _connect(
            ExternalIntegrationId.LOCAL_MODELS,
            {"server_url": "http://server:8080", "api_key": "  "},
        )
        await call
        assert integration.payloads == [{"server_url": "http://server:8080"}]

    @pytest.mark.asyncio
    async def test_custom_endpoint_requires_base_url(self):
        call, port, integration = _connect(
            ExternalIntegrationId.OPENAI_COMPATIBLE, {"api_key": "x"}
        )
        with pytest.raises(IntegrationSetupError) as error:
            await call
        assert error.value.code == IntegrationSetupErrorCode.INVALID_CREDENTIALS
        assert integration.payloads == []
        port.activate.assert_not_called()

    @pytest.mark.asyncio
    async def test_custom_endpoint_key_is_optional(self):
        call, port, integration = _connect(
            ExternalIntegrationId.OPENAI_COMPATIBLE,
            {"base_url": "http://localhost:1234", "api_key": ""},
        )
        await call
        assert integration.payloads == [{"base_url": "http://localhost:1234"}]

    @pytest.mark.asyncio
    async def test_required_fields_are_still_enforced(self):
        call, port, integration = _connect(ExternalIntegrationId.OPENAI, {})
        with pytest.raises(IntegrationSetupError):
            await call


class TestDisconnectTeardown:
    @pytest.mark.asyncio
    async def test_tears_down_integration(self):
        port = AsyncMock()
        integration = FakeIntegration()
        await DisconnectExternalIntegrationImpl(
            port, {ExternalIntegrationId.LOCAL_MODELS: integration}
        ).execute(DisconnectedExternalIntegrationRequest("LOCAL_MODELS"))
        port.deactivate.assert_awaited_once_with(ExternalIntegrationId.LOCAL_MODELS)
        assert integration.teardowns == 1

    @pytest.mark.asyncio
    async def test_teardown_errors_are_ignored(self):
        port = AsyncMock()
        integration = FakeIntegration(error=RuntimeError("boom"))
        await DisconnectExternalIntegrationImpl(
            port, {ExternalIntegrationId.LOCAL_MODELS: integration}
        ).execute(DisconnectedExternalIntegrationRequest("LOCAL_MODELS"))
        port.deactivate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_without_registered_integration(self):
        port = AsyncMock()
        await DisconnectExternalIntegrationImpl(port, {}).execute(
            DisconnectedExternalIntegrationRequest("OPENAI")
        )
        port.deactivate.assert_awaited_once_with(ExternalIntegrationId.OPENAI)


class TestGetIntegrationsOptionalFields:
    @pytest.mark.asyncio
    async def test_serializes_shared_family_metadata_for_related_methods(self):
        port = AsyncMock()
        port.get_all.return_value = [
            ExternalIntegration(
                id=integration_id,
                name=integration_id.value,
                type=ExternalIntegrationType.AI_PROVIDER
                if integration_id != ExternalIntegrationId.GOOGLE_SHEETS
                else ExternalIntegrationType.DATA_SOURCE,
                status=ExternalIntegrationStatus.OFF,
            )
            for integration_id in (
                ExternalIntegrationId.OPENAI,
                ExternalIntegrationId.CHATGPT,
                ExternalIntegrationId.GOOGLE_SHEETS,
            )
        ]
        result = asdict(await GetExternalIntegrationsImpl(port, {}).execute())
        by_id = {
            integration["id"]: integration for integration in result["integrations"]
        }
        assert by_id[ExternalIntegrationId.OPENAI]["family"] == {
            "id": "OPENAI",
            "name": "OpenAI",
        }
        assert (
            by_id[ExternalIntegrationId.CHATGPT]["family"]
            == by_id[ExternalIntegrationId.OPENAI]["family"]
        )
        assert by_id[ExternalIntegrationId.GOOGLE_SHEETS]["family"] is None

    def test_mobile_platforms_match_registered_ai_clients(self):
        root = Path(__file__).resolve().parents[4]
        module = ast.parse(
            (root / "frontend/app/src/python/finanze/app_lazy.py").read_text()
        )
        clients = next(
            node
            for node in ast.walk(module)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "ai_clients"
                for target in node.targets
            )
        )
        registered = {ExternalIntegrationId(key.attr) for key in clients.value.keys}
        declared = {
            provider
            for provider, platforms in AI_PROVIDER_PLATFORMS.items()
            if IntegrationPlatform.MOBILE in platforms
        }
        assert declared == registered

    @pytest.mark.asyncio
    async def test_exposes_optional_fields(self):
        port = AsyncMock()
        port.get_all.return_value = [
            ExternalIntegration(
                id=integration_id,
                name=integration_id.value,
                type=ExternalIntegrationType.AI_PROVIDER,
                status=ExternalIntegrationStatus.OFF,
            )
            for integration_id in (
                ExternalIntegrationId.OPENAI,
                ExternalIntegrationId.OPENAI_COMPATIBLE,
                ExternalIntegrationId.LOCAL_MODELS,
            )
        ]
        result = await GetExternalIntegrationsImpl(
            port, {ExternalIntegrationId.OPENAI_COMPATIBLE: FakeIntegration()}
        ).execute()
        by_id = {i.id: i for i in result.integrations}
        assert by_id[ExternalIntegrationId.OPENAI].optional_fields is None
        assert by_id[ExternalIntegrationId.OPENAI_COMPATIBLE].optional_fields == [
            "api_key"
        ]
        assert by_id[ExternalIntegrationId.OPENAI_COMPATIBLE].payload_schema == {
            "base_url": "Base URL",
            "api_key": "API Key",
        }
        assert by_id[ExternalIntegrationId.LOCAL_MODELS].optional_fields == [
            "api_key",
            "server_url",
        ]
        assert by_id[ExternalIntegrationId.LOCAL_MODELS].available is False
        assert asdict(by_id[ExternalIntegrationId.OPENAI].family) == {
            "id": AIProviderFamily.OPENAI.value,
            "name": "OpenAI",
        }
        assert by_id[ExternalIntegrationId.OPENAI].platforms == list(
            IntegrationPlatform
        )
        assert (
            IntegrationPlatform.MOBILE
            not in by_id[ExternalIntegrationId.LOCAL_MODELS].platforms
        )
