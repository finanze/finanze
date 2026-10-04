import json
from datetime import date
from typing import Optional
from uuid import uuid4

import pytest
from application.ports.ai_client import AIClient
from domain.ai import (
    AIClientFeature,
    AIDecisionAnswer,
    AIDecisionRequest,
    AIDecisionResult,
    AIGeneration,
    AIGenerationRequest,
    AIGenerationStatus,
    AIModel,
    AIModelCapability,
    AIModelProvider,
    AIReasoningEffort,
)
from domain.dezimal import Dezimal
from domain.exception.exceptions import (
    AIProviderError,
    AIProviderErrorCode,
    ExternalLabelingUnavailable,
)
from domain.external_integration import ExternalIntegrationId
from domain.external_labeling import (
    ExternalLabelCandidate,
    ExternalLabelingExample,
    ExternalLabelingModel,
    ExternalLabelingRequest,
    ExternalLabelingTx,
)
from domain.transactions import TxType
from infrastructure.labeling.ai_labeling_presets import (
    LABELING_PRESETS,
    AILabelingPreset,
)
from infrastructure.labeling.ai_labeling_provider import (
    DECISIONS_BATCH_SIZE,
    GENERATION_BATCH_SIZE,
    AILabelingProvider,
)

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


class FakeAIClient(AIClient):
    def __init__(
        self,
        features: set = None,
        models: Optional[dict] = None,
        providers: Optional[list[AIModelProvider]] = None,
        generation: Optional[AIGeneration] = None,
        error: Optional[Exception] = None,
    ):
        self._features = features if features is not None else ALL_FEATURES
        self.models = models or {}
        self.providers = providers or []
        self.generation = generation
        self.error = error
        self.get_model_calls = 0
        self.generate_requests: list[AIGenerationRequest] = []
        self.decide_requests: list[AIDecisionRequest] = []

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
        return self.providers

    async def generate(self, request, credentials):
        self.generate_requests.append(request)
        if self.error:
            raise self.error
        if self.generation is not None:
            return self.generation
        ids = [f"m{i + 1}" for i in range(len(json.loads(request.messages[0].content)))]
        return AIGeneration(
            status=AIGenerationStatus.COMPLETED,
            text=json.dumps(
                {
                    "results": [
                        {"id": movement_id, "category": "groceries", "confidence": 0.8}
                        for movement_id in ids
                    ]
                }
            ),
        )

    async def decide(self, request, credentials):
        self.decide_requests.append(request)
        if self.error:
            raise self.error
        return AIDecisionResult(
            answers={
                question.id: AIDecisionAnswer(
                    choice="groceries", probabilities={"groceries": Dezimal("0.7")}
                )
                for question in request.questions
            }
        )


def _tx(name: str = "MERCADONA") -> ExternalLabelingTx:
    return ExternalLabelingTx(
        id=uuid4(),
        date=date(2025, 1, 10),
        type=TxType.FEE,
        amount=Dezimal("-12.5"),
        currency="EUR",
        name=name,
    )


GROCERIES = ExternalLabelCandidate(id=uuid4(), key="groceries")
CUSTOM = ExternalLabelCandidate(id=uuid4(), name="Pets", description="Vet and food")


def _request(model: str, count: int = 1, **kwargs) -> ExternalLabelingRequest:
    return ExternalLabelingRequest(
        model=model,
        txs=[_tx(f"TX {i}") for i in range(count)],
        labels=[GROCERIES, CUSTOM],
        **kwargs,
    )


def _provider(client: AIClient, presets=None) -> AILabelingProvider:
    return AILabelingProvider(client, presets or [])


class TestRecommendedModels:
    def test_returns_preset_models(self):
        provider = _provider(
            FakeAIClient(), LABELING_PRESETS[ExternalIntegrationId.OPENAI]
        )
        models = provider.get_recommended_models()
        assert [m.id for m in models] == ["gpt-6-luna"]
        assert models[0].probabilistic is False

    def test_upstream_support_depends_on_client_features(self):
        assert _provider(FakeAIClient()).supports_upstream_providers()
        assert not _provider(
            FakeAIClient(features={AIClientFeature.GENERATION})
        ).supports_upstream_providers()


class TestLabel:
    @pytest.mark.asyncio
    async def test_model_info_is_cached(self):
        client = FakeAIClient(models={"gen": GENERATION_MODEL})
        provider = _provider(client)
        await provider.label(_request("gen"), CREDENTIALS)
        await provider.label(_request("gen"), CREDENTIALS)
        assert client.get_model_calls == 1

    @pytest.mark.asyncio
    async def test_empty_request_skips_calls(self):
        client = FakeAIClient(models={"gen": GENERATION_MODEL})
        provider = _provider(client)
        request = ExternalLabelingRequest(model="gen", txs=[], labels=[GROCERIES])
        assert await provider.label(request, CREDENTIALS) == []
        assert client.get_model_calls == 0
        assert client.generate_requests == []

    @pytest.mark.asyncio
    async def test_generation_batches_and_parses(self):
        client = FakeAIClient(models={"gen": GENERATION_MODEL})
        request = _request("gen", GENERATION_BATCH_SIZE + 1)
        suggestions = await _provider(client).label(request, CREDENTIALS)
        assert len(client.generate_requests) == 2
        assert client.decide_requests == []
        assert [s.tx_id for s in suggestions] == [tx.id for tx in request.txs]
        assert all(s.label_id == GROCERIES.id for s in suggestions)
        assert all(s.confidence == Dezimal("0.8") for s in suggestions)

    @pytest.mark.asyncio
    async def test_decisions_batches_and_parses(self):
        client = FakeAIClient(models={"dec": DECISIONS_MODEL})
        request = _request("dec", DECISIONS_BATCH_SIZE + 1)
        suggestions = await _provider(client).label(request, CREDENTIALS)
        assert len(client.decide_requests) == 2
        assert client.generate_requests == []
        assert len(suggestions) == DECISIONS_BATCH_SIZE + 1
        assert suggestions[0].confidence == Dezimal("0.7")

    @pytest.mark.asyncio
    async def test_generation_request_settings(self):
        client = FakeAIClient(models={"gen": GENERATION_MODEL})
        preset = AILabelingPreset(
            model=ExternalLabelingModel(id="gen", name="Gen"),
            reasoning_effort=AIReasoningEffort.NONE,
        )
        await _provider(client, [preset]).label(
            _request("gen", instructions="Pets are vet bills"), CREDENTIALS
        )
        sent = client.generate_requests[0]
        assert sent.temperature == Dezimal(0)
        assert sent.reasoning_effort == AIReasoningEffort.NONE
        assert sent.upstream_provider is None
        assert "Pets are vet bills" in sent.instructions
        assert "custom_pets" in sent.instructions
        assert sent.response_schema.schema["properties"]["results"]["items"][
            "properties"
        ]["category"]["enum"] == ["groceries", "custom_pets", "none"]

    @pytest.mark.asyncio
    async def test_no_temperature_without_capability(self):
        client = FakeAIClient(
            models={
                "gen": AIModel(
                    id="gen",
                    name="Gen",
                    capabilities={AIModelCapability.STRUCTURED_OUTPUT},
                )
            }
        )
        await _provider(client).label(_request("gen"), CREDENTIALS)
        assert client.generate_requests[0].temperature is None
        assert client.generate_requests[0].reasoning_effort is None

    @pytest.mark.asyncio
    async def test_examples_are_included(self):
        client = FakeAIClient(models={"gen": GENERATION_MODEL})
        request = _request(
            "gen",
            examples=[
                ExternalLabelingExample(tx=_tx("LIDL"), label_ids=[GROCERIES.id]),
                ExternalLabelingExample(tx=_tx("UNKNOWN"), label_ids=[uuid4()]),
            ],
        )
        await _provider(client).label(request, CREDENTIALS)
        instructions = client.generate_requests[0].instructions
        assert "LIDL" in instructions
        assert "UNKNOWN" not in instructions

    @pytest.mark.asyncio
    async def test_upstream_provider_is_forwarded(self):
        client = FakeAIClient(models={"gen": GENERATION_MODEL})
        await _provider(client).label(
            _request("gen", upstream_provider="openai"), CREDENTIALS
        )
        assert client.generate_requests[0].upstream_provider == "openai"

    @pytest.mark.asyncio
    async def test_ignores_none_unknown_and_clamps_confidence(self):
        request = _request("gen", 3)
        client = FakeAIClient(
            models={"gen": GENERATION_MODEL},
            generation=AIGeneration(
                status=AIGenerationStatus.COMPLETED,
                text=json.dumps(
                    {
                        "results": [
                            {"id": "m1", "category": "custom_pets", "confidence": 3},
                            {"id": "m2", "category": "none", "confidence": 0.9},
                            {"id": "m9", "category": "groceries", "confidence": 0.9},
                            {"id": "m3", "category": "groceries", "confidence": -1},
                        ]
                    }
                ),
            ),
        )
        suggestions = await _provider(client).label(request, CREDENTIALS)
        assert [(s.tx_id, s.label_id, s.confidence) for s in suggestions] == [
            (request.txs[0].id, CUSTOM.id, Dezimal(1)),
            (request.txs[2].id, GROCERIES.id, Dezimal(0)),
        ]

    @pytest.mark.parametrize(
        "generation",
        [
            AIGeneration(status=AIGenerationStatus.COMPLETED, text="not json"),
            AIGeneration(status=AIGenerationStatus.REFUSED, refusal="No"),
            AIGeneration(status=AIGenerationStatus.INCOMPLETE, text='{"res'),
        ],
    )
    @pytest.mark.asyncio
    async def test_unusable_generation_returns_nothing(self, generation):
        client = FakeAIClient(models={"gen": GENERATION_MODEL}, generation=generation)
        assert await _provider(client).label(_request("gen"), CREDENTIALS) == []

    @pytest.mark.asyncio
    async def test_provider_error_raises_unavailable(self):
        client = FakeAIClient(
            models={"gen": GENERATION_MODEL},
            error=AIProviderError(AIProviderErrorCode.INSUFFICIENT_FUNDS, "No funds"),
        )
        with pytest.raises(ExternalLabelingUnavailable):
            await _provider(client).label(_request("gen"), CREDENTIALS)

    @pytest.mark.asyncio
    async def test_falls_back_to_probabilistic_preset_without_model_info(self):
        client = FakeAIClient()
        await _provider(
            client, LABELING_PRESETS[ExternalIntegrationId.OPENROUTER]
        ).label(_request("~typesafe/jev-latest"), CREDENTIALS)
        assert len(client.decide_requests) == 1

    @pytest.mark.asyncio
    async def test_falls_back_to_generation_without_model_info(self):
        client = FakeAIClient(features={AIClientFeature.GENERATION})
        await _provider(client, LABELING_PRESETS[ExternalIntegrationId.OPENAI]).label(
            _request("gpt-6-luna"), CREDENTIALS
        )
        sent = client.generate_requests[0]
        assert sent.temperature is None
        assert sent.reasoning_effort == AIReasoningEffort.NONE
