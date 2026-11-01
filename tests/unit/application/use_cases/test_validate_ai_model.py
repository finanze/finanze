from typing import Optional
from unittest.mock import AsyncMock

import pytest
from application.ports.ai_client import AIClient
from application.ports.external_integration_port import ExternalIntegrationPort
from application.use_cases.validate_ai_model import ValidateAIModelImpl
from domain.ai import (
    AIClientFeature,
    AIModel,
    AIModelCapability,
    AIModelProvider,
    AIModelValidation,
    AITask,
    ValidateAIModelRequest,
)
from domain.exception.exceptions import (
    AIProviderError,
    AIProviderErrorCode,
    IntegrationNotFound,
)
from domain.external_integration import ExternalIntegrationId

CREDENTIALS = {"api_key": "key"}
ALL_FEATURES = {
    AIClientFeature.GENERATION,
    AIClientFeature.DECISIONS,
    AIClientFeature.UPSTREAM_PROVIDERS,
}
GENERATION_MODEL = AIModel(
    id="gen",
    name="Gen",
    capabilities={AIModelCapability.STRUCTURED_OUTPUT, AIModelCapability.TEMPERATURE},
)
DECISIONS_MODEL = AIModel(
    id="dec", name="Dec", capabilities={AIModelCapability.DECISIONS}
)
UPSTREAM_PROVIDERS = [
    AIModelProvider(
        id="openai/flex",
        capabilities={AIModelCapability.STRUCTURED_OUTPUT},
    ),
    AIModelProvider(id="azure"),
    AIModelProvider(
        id="deepinfra",
        capabilities={AIModelCapability.STRUCTURED_OUTPUT},
    ),
]


class FakeAIClient(AIClient):
    def __init__(
        self,
        features: Optional[set] = None,
        models: Optional[dict] = None,
        providers=None,
    ):
        self._features = features if features is not None else ALL_FEATURES
        self.models = models or {}
        self.providers = providers if providers is not None else []
        self.get_model_calls = 0

    async def setup(self, payload):
        pass

    def features(self):
        return self._features

    async def get_model(self, model_id, credentials):
        self.get_model_calls += 1
        model = self.models.get(model_id)
        if isinstance(model, Exception):
            raise model
        return model

    async def get_model_providers(self, model_id, credentials):
        if isinstance(self.providers, Exception):
            raise self.providers
        return self.providers

    async def generate(self, request, credentials):
        raise NotImplementedError


def _use_case(client: AIClient) -> ValidateAIModelImpl:
    port = AsyncMock(spec=ExternalIntegrationPort)
    port.get_payload = AsyncMock(return_value=CREDENTIALS)
    return ValidateAIModelImpl(port, {ExternalIntegrationId.OPENROUTER: client})


async def _validate(
    client: AIClient, model: str, upstream: Optional[str] = None
) -> AIModelValidation:
    return await _use_case(client).execute(
        ValidateAIModelRequest(
            provider=ExternalIntegrationId.OPENROUTER,
            model=model,
            task=AITask.LABELING,
            upstream_provider=upstream,
        )
    )


class TestValidateAIModel:
    @pytest.mark.asyncio
    async def test_structured_output_model_is_valid(self):
        result = await _validate(FakeAIClient(models={"gen": GENERATION_MODEL}), "gen")
        assert result == AIModelValidation(
            valid=True,
            name="Gen",
            capabilities=[
                AIModelCapability.STRUCTURED_OUTPUT,
                AIModelCapability.TEMPERATURE,
            ],
        )

    @pytest.mark.asyncio
    async def test_model_id_is_trimmed(self):
        client = FakeAIClient(models={"gen": GENERATION_MODEL})
        assert (await _validate(client, "  gen  ")).valid

    @pytest.mark.asyncio
    async def test_decisions_model_is_valid(self):
        result = await _validate(FakeAIClient(models={"dec": DECISIONS_MODEL}), "dec")
        assert result.valid
        assert result.capabilities == [AIModelCapability.DECISIONS]

    @pytest.mark.asyncio
    async def test_decisions_model_without_client_support_is_invalid(self):
        client = FakeAIClient(
            features={AIClientFeature.GENERATION}, models={"dec": DECISIONS_MODEL}
        )
        result = await _validate(client, "dec")
        assert not result.valid
        assert result.capabilities == []

    @pytest.mark.asyncio
    async def test_model_without_structured_output_is_invalid(self):
        client = FakeAIClient(models={"img": AIModel(id="img", name="Img")})
        result = await _validate(client, "img")
        assert not result.valid
        assert result.name == "Img"

    @pytest.mark.asyncio
    async def test_unknown_model_is_invalid(self):
        assert await _validate(FakeAIClient(), "x") == AIModelValidation(valid=False)

    @pytest.mark.asyncio
    async def test_model_fetch_failure_is_invalid(self):
        client = FakeAIClient(
            models={"gen": AIProviderError(AIProviderErrorCode.UNAVAILABLE, "down")}
        )
        assert not (await _validate(client, "gen")).valid

    @pytest.mark.parametrize("model", ["", "   ", "x" * 201])
    @pytest.mark.asyncio
    async def test_invalid_model_id_skips_lookup(self, model):
        client = FakeAIClient(models={"gen": GENERATION_MODEL})
        assert not (await _validate(client, model)).valid
        assert client.get_model_calls == 0

    @pytest.mark.asyncio
    async def test_unknown_provider_raises(self):
        with pytest.raises(IntegrationNotFound):
            await _use_case(FakeAIClient()).execute(
                ValidateAIModelRequest(
                    provider=ExternalIntegrationId.OPENAI,
                    model="gen",
                    task=AITask.LABELING,
                )
            )


class TestUpstreamProvider:
    @pytest.mark.parametrize("upstream", ["openai/flex", "OpenAI", "openai"])
    @pytest.mark.asyncio
    async def test_available_upstream_provider(self, upstream):
        client = FakeAIClient(
            models={"gen": GENERATION_MODEL}, providers=UPSTREAM_PROVIDERS
        )
        result = await _validate(client, "gen", upstream)
        assert result.valid
        assert result.upstream_provider == "openai/flex"
        assert result.capabilities == [AIModelCapability.STRUCTURED_OUTPUT]

    @pytest.mark.parametrize("upstream", ["azure", "deepinfra/fp8", "flex"])
    @pytest.mark.asyncio
    async def test_unavailable_upstream_provider(self, upstream):
        client = FakeAIClient(
            models={"gen": GENERATION_MODEL}, providers=UPSTREAM_PROVIDERS
        )
        result = await _validate(client, "gen", upstream)
        assert not result.valid
        assert result.upstream_provider is None

    @pytest.mark.asyncio
    async def test_first_capable_matching_upstream_is_selected(self):
        client = FakeAIClient(
            models={"gen": GENERATION_MODEL},
            providers=[
                AIModelProvider(id="openai/default"),
                AIModelProvider(
                    id="openai/flex",
                    capabilities={AIModelCapability.STRUCTURED_OUTPUT},
                ),
            ],
        )
        result = await _validate(client, "gen", "openai")
        assert result.upstream_provider == "openai/flex"

    @pytest.mark.asyncio
    async def test_upstream_rejected_without_client_support(self):
        client = FakeAIClient(
            features={AIClientFeature.GENERATION},
            models={"gen": GENERATION_MODEL},
            providers=UPSTREAM_PROVIDERS,
        )
        result = await _validate(client, "gen", "openai")
        assert not result.valid
        assert client.get_model_calls == 0

    @pytest.mark.asyncio
    async def test_upstream_rejected_for_decisions_model(self):
        client = FakeAIClient(
            models={"dec": DECISIONS_MODEL},
            providers=[
                AIModelProvider(
                    id="typesafe",
                    capabilities={AIModelCapability.STRUCTURED_OUTPUT},
                )
            ],
        )
        assert not (await _validate(client, "dec", "typesafe")).valid

    @pytest.mark.asyncio
    async def test_upstream_fetch_failure_is_invalid(self):
        client = FakeAIClient(
            models={"gen": GENERATION_MODEL},
            providers=AIProviderError(AIProviderErrorCode.UNAVAILABLE, "down"),
        )
        assert not (await _validate(client, "gen", "openai")).valid

    @pytest.mark.asyncio
    async def test_too_long_upstream_is_invalid(self):
        client = FakeAIClient(
            models={"gen": GENERATION_MODEL}, providers=UPSTREAM_PROVIDERS
        )
        assert not (await _validate(client, "gen", "o" * 201)).valid
        assert client.get_model_calls == 0
