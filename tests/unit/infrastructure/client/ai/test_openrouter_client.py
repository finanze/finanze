from unittest.mock import AsyncMock

import httpx
import pytest
from domain.ai import (
    AIChoiceQuestion,
    AIClientFeature,
    AIDecisionRequest,
    AIGenerationRequest,
    AIGenerationStatus,
    AIJsonSchema,
    AIMessage,
    AIMessageRole,
    AIModelCapability,
    AIReasoningEffort,
)
from domain.dezimal import Dezimal
from domain.exception.exceptions import (
    AIProviderError,
    AIProviderErrorCode,
    IntegrationSetupError,
    TooManyRequests,
)
from infrastructure.client.ai.openrouter.openrouter_client import OpenRouterClient
from infrastructure.client.http.http_response import HttpResponse

CREDENTIALS = {"api_key": "sk-or-v1-x"}


def _response(status: int, body: dict) -> HttpResponse:
    return HttpResponse(httpx.Response(status, json=body))


def _client(*responses: tuple[int, dict]) -> OpenRouterClient:
    client = OpenRouterClient()
    client.BACKOFF_SECONDS = 0
    client._session = AsyncMock()
    client._session.request.side_effect = [
        _response(status, body) for status, body in responses
    ]
    return client


def _sent(client: OpenRouterClient, index: int = 0):
    call = client._session.request.call_args_list[index]
    return call.args[0], call.args[1], call.kwargs


def _request(**kwargs) -> AIGenerationRequest:
    return AIGenerationRequest(
        model="openai/gpt-6-luna",
        messages=[AIMessage(role=AIMessageRole.USER, content="hello")],
        **kwargs,
    )


def _completion(message: dict, finish_reason: str = "stop", usage=None) -> dict:
    body = {"choices": [{"message": message, "finish_reason": finish_reason}]}
    if usage is not None:
        body["usage"] = usage
    return body


class TestOpenRouterClientSetup:
    @pytest.mark.asyncio
    async def test_accepts_inference_key(self):
        client = _client((200, {"data": {"is_management_key": False}}))
        await client.setup(CREDENTIALS)
        method, url, kwargs = _sent(client)
        assert method == "GET"
        assert url == "https://openrouter.ai/api/v1/key"
        assert kwargs["headers"]["Authorization"] == "Bearer sk-or-v1-x"
        assert kwargs["headers"]["X-Title"] == "Finanze"

    @pytest.mark.asyncio
    async def test_rejects_management_key(self):
        client = _client((200, {"data": {"is_management_key": True}}))
        with pytest.raises(IntegrationSetupError):
            await client.setup(CREDENTIALS)

    @pytest.mark.asyncio
    async def test_rejects_legacy_provisioning_key(self):
        client = _client((200, {"data": {"is_provisioning_key": True}}))
        with pytest.raises(IntegrationSetupError):
            await client.setup(CREDENTIALS)

    @pytest.mark.asyncio
    async def test_rejects_unauthorized_key(self):
        client = _client((401, {"error": {"code": 401, "message": "User not found"}}))
        with pytest.raises(IntegrationSetupError):
            await client.setup(CREDENTIALS)


class TestOpenRouterClientFeatures:
    def test_supports_all_features(self):
        assert OpenRouterClient().features() == {
            AIClientFeature.GENERATION,
            AIClientFeature.DECISIONS,
            AIClientFeature.UPSTREAM_PROVIDERS,
        }


class TestOpenRouterClientGetModel:
    @pytest.mark.asyncio
    async def test_maps_text_model_capabilities(self):
        client = _client(
            (
                200,
                {
                    "data": {
                        "name": "GPT-6 Luna",
                        "architecture": {"output_modalities": ["text"]},
                        "supported_parameters": [
                            "response_format",
                            "temperature",
                            "reasoning",
                        ],
                    }
                },
            )
        )
        model = await client.get_model("openai/gpt-6-luna", CREDENTIALS)
        assert model.name == "GPT-6 Luna"
        assert model.capabilities == {
            AIModelCapability.STRUCTURED_OUTPUT,
            AIModelCapability.TEMPERATURE,
            AIModelCapability.REASONING,
        }
        assert _sent(client)[1].endswith("/model/openai/gpt-6-luna")

    @pytest.mark.asyncio
    async def test_maps_decisions_model(self):
        client = _client(
            (
                200,
                {
                    "data": {
                        "name": "Jev",
                        "architecture": {"output_modalities": ["decisions"]},
                        "supported_parameters": ["temperature"],
                    }
                },
            )
        )
        model = await client.get_model("~typesafe/jev-latest", CREDENTIALS)
        assert model.capabilities == {AIModelCapability.DECISIONS}
        assert _sent(client)[1].endswith("/model/~typesafe/jev-latest")

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        client = _client((404, {"error": {"message": "Not found"}}))
        assert await client.get_model("openai/missing", CREDENTIALS) is None

    @pytest.mark.asyncio
    async def test_returns_none_without_author(self):
        client = _client()
        assert await client.get_model("gpt-6-luna", CREDENTIALS) is None
        client._session.request.assert_not_called()


class TestOpenRouterClientModelProviders:
    @pytest.mark.asyncio
    async def test_maps_endpoints(self):
        client = _client(
            (
                200,
                {
                    "data": {
                        "endpoints": [
                            {
                                "tag": "openai/flex",
                                "supported_parameters": ["structured_outputs"],
                            },
                            {"tag": "azure", "supported_parameters": []},
                            {"supported_parameters": ["structured_outputs"]},
                        ]
                    }
                },
            )
        )
        providers = await client.get_model_providers("openai/gpt-6-luna", CREDENTIALS)
        assert [p.id for p in providers] == ["openai/flex", "azure"]
        assert providers[0].capabilities == {AIModelCapability.STRUCTURED_OUTPUT}
        assert providers[1].capabilities == set()
        assert _sent(client)[1].endswith("/models/openai/gpt-6-luna/endpoints")


class TestOpenRouterClientGenerate:
    @pytest.mark.asyncio
    async def test_builds_chat_completion_body(self):
        client = _client((200, _completion({"content": "{}"})))
        await client.generate(
            _request(
                instructions="Be precise",
                response_schema=AIJsonSchema(name="results", schema={"type": "object"}),
                temperature=Dezimal(0),
                reasoning_effort=AIReasoningEffort.EXTRA_HIGH,
                max_output_tokens=100,
                upstream_provider="openai",
            ),
            CREDENTIALS,
        )
        method, url, kwargs = _sent(client)
        body = kwargs["json"]
        assert method == "POST"
        assert url.endswith("/chat/completions")
        assert body["messages"] == [
            {"role": "system", "content": "Be precise"},
            {"role": "user", "content": "hello"},
        ]
        assert body["response_format"] == {
            "type": "json_schema",
            "json_schema": {
                "name": "results",
                "strict": True,
                "schema": {"type": "object"},
            },
        }
        assert body["temperature"] == 0.0
        assert body["reasoning"] == {"effort": "xhigh"}
        assert body["max_tokens"] == 100
        assert body["provider"] == {"order": ["openai"], "allow_fallbacks": False}

    @pytest.mark.asyncio
    async def test_omits_optional_fields(self):
        client = _client((200, _completion({"content": "{}"})))
        await client.generate(_request(), CREDENTIALS)
        body = _sent(client)[2]["json"]
        assert set(body) == {"model", "messages"}

    @pytest.mark.asyncio
    async def test_maps_completed_response(self):
        client = _client(
            (
                200,
                _completion(
                    {"content": '{"results": []}'},
                    usage={"prompt_tokens": 10, "completion_tokens": 3},
                ),
            )
        )
        generation = await client.generate(_request(), CREDENTIALS)
        assert generation.status == AIGenerationStatus.COMPLETED
        assert generation.text == '{"results": []}'
        assert generation.usage.input_tokens == 10
        assert generation.usage.output_tokens == 3

    @pytest.mark.asyncio
    async def test_maps_refusal(self):
        client = _client((200, _completion({"content": None, "refusal": "No"})))
        generation = await client.generate(_request(), CREDENTIALS)
        assert generation.status == AIGenerationStatus.REFUSED
        assert generation.refusal == "No"
        assert generation.text is None

    @pytest.mark.asyncio
    async def test_maps_truncated_response(self):
        client = _client((200, _completion({"content": '{"res'}, "length")))
        generation = await client.generate(_request(), CREDENTIALS)
        assert generation.status == AIGenerationStatus.INCOMPLETE


class TestOpenRouterClientDecide:
    @pytest.mark.asyncio
    async def test_maps_questions_and_answers(self):
        client = _client(
            (
                200,
                {
                    "answers": {
                        "m1": {
                            "choice": "food",
                            "confidence": 0.9,
                            "probabilities": {"food": 0.9, "none": "bad"},
                        },
                        "m2": "invalid",
                    }
                },
            )
        )
        result = await client.decide(
            AIDecisionRequest(
                model="~typesafe/jev-latest",
                state={"movements": []},
                questions=[
                    AIChoiceQuestion(
                        id="m1", instructions="Pick", options=["food", "none"]
                    )
                ],
            ),
            CREDENTIALS,
        )
        body = _sent(client)[2]["json"]
        assert _sent(client)[1].endswith("/systemone")
        assert body["questions"] == {
            "m1": {
                "type": "choice",
                "instructions": "Pick",
                "criteria": {"food": None, "none": None},
            }
        }
        assert list(result.answers) == ["m1"]
        answer = result.answers["m1"]
        assert answer.choice == "food"
        assert answer.confidence == Dezimal("0.9")
        assert answer.probabilities == {"food": Dezimal("0.9")}


class TestOpenRouterClientErrors:
    @pytest.mark.asyncio
    async def test_unauthorized_raises_invalid_credentials(self):
        client = _client((401, {"error": {"code": 401, "message": "User not found"}}))
        with pytest.raises(AIProviderError) as error:
            await client.generate(_request(), CREDENTIALS)
        assert error.value.code == AIProviderErrorCode.INVALID_CREDENTIALS

    @pytest.mark.asyncio
    async def test_payment_required_raises_insufficient_funds(self):
        client = _client((402, {"error": {"code": 402, "message": "No credits"}}))
        with pytest.raises(AIProviderError) as error:
            await client.generate(_request(), CREDENTIALS)
        assert error.value.code == AIProviderErrorCode.INSUFFICIENT_FUNDS

    @pytest.mark.asyncio
    async def test_server_error_raises_unavailable(self):
        client = _client((500, {"error": {"message": "Boom"}}))
        with pytest.raises(AIProviderError) as error:
            await client.generate(_request(), CREDENTIALS)
        assert error.value.code == AIProviderErrorCode.UNAVAILABLE

    @pytest.mark.asyncio
    async def test_retries_transient_errors(self):
        client = _client(
            (503, {"error": {"message": "Overloaded"}}),
            (200, _completion({"content": "{}"})),
        )
        generation = await client.generate(_request(), CREDENTIALS)
        assert generation.status == AIGenerationStatus.COMPLETED
        assert client._session.request.call_count == 2

    @pytest.mark.asyncio
    async def test_rate_limit_after_retries_raises_too_many_requests(self):
        limited = (429, {"error": {"message": "Slow down"}})
        client = _client(*[limited] * (OpenRouterClient.MAX_RETRIES + 1))
        with pytest.raises(TooManyRequests):
            await client.generate(_request(), CREDENTIALS)
        assert client._session.request.call_count == OpenRouterClient.MAX_RETRIES + 1
