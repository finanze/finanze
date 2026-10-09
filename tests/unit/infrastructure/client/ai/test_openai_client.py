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
from infrastructure.client.ai.openai.openai_client import OpenAIClient
from infrastructure.client.http.http_response import HttpResponse

CREDENTIALS = {"api_key": "sk-proj-x"}
QUOTA_ERROR = {
    "error": {
        "message": "You exceeded your current quota",
        "type": "insufficient_quota",
        "code": "insufficient_quota",
    }
}


def _client(*responses: tuple[int, dict]) -> OpenAIClient:
    client = OpenAIClient()
    client.BACKOFF_SECONDS = 0
    client._session = AsyncMock()
    client._session.request.side_effect = [
        HttpResponse(httpx.Response(status, json=body)) for status, body in responses
    ]
    return client


def _sent(client: OpenAIClient, index: int = 0):
    call = client._session.request.call_args_list[index]
    return call.args[0], call.args[1], call.kwargs


def _request(**kwargs) -> AIGenerationRequest:
    return AIGenerationRequest(
        model="gpt-6-luna",
        messages=[AIMessage(role=AIMessageRole.USER, content="hello")],
        **kwargs,
    )


def _output(*parts: dict, response_status: str = "completed", usage=None) -> dict:
    body = {
        "status": response_status,
        "output": [
            {"type": "reasoning", "summary": []},
            {"type": "message", "role": "assistant", "content": list(parts)},
        ],
    }
    if usage is not None:
        body["usage"] = usage
    return body


def _text(text: str) -> dict:
    return {"type": "output_text", "text": text, "annotations": []}


class TestOpenAIClientSetup:
    @pytest.mark.asyncio
    async def test_accepts_valid_key(self):
        client = _client((200, {"object": "list", "data": []}))
        await client.setup(CREDENTIALS)
        method, url, kwargs = _sent(client)
        assert method == "GET"
        assert url == "https://api.openai.com/v1/models"
        assert kwargs["headers"]["Authorization"] == "Bearer sk-proj-x"

    @pytest.mark.parametrize("status", [401, 403])
    @pytest.mark.asyncio
    async def test_rejects_invalid_key(self, status):
        client = _client((status, {"error": {"message": "Incorrect API key"}}))
        with pytest.raises(IntegrationSetupError):
            await client.setup(CREDENTIALS)

    @pytest.mark.asyncio
    async def test_rate_limited_setup(self):
        limited = (429, {"error": {"message": "Slow down"}})
        client = _client(*[limited] * (OpenAIClient.MAX_RETRIES + 1))
        with pytest.raises(TooManyRequests):
            await client.setup(CREDENTIALS)


class TestOpenAIClientFeatures:
    def test_supports_generation_only(self):
        assert OpenAIClient().features() == {AIClientFeature.GENERATION}

    @pytest.mark.asyncio
    async def test_decide_is_unsupported(self):
        client = _client()
        with pytest.raises(AIProviderError) as error:
            await client.decide(
                AIDecisionRequest(
                    model="gpt-6-luna",
                    state={},
                    questions=[
                        AIChoiceQuestion(id="q", instructions="Pick", options=["a"])
                    ],
                ),
                CREDENTIALS,
            )
        assert error.value.code == AIProviderErrorCode.UNSUPPORTED_OPERATION
        client._session.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_model_providers_are_unsupported(self):
        with pytest.raises(AIProviderError) as error:
            await _client().get_model_providers("gpt-6-luna", CREDENTIALS)
        assert error.value.code == AIProviderErrorCode.UNSUPPORTED_OPERATION


class TestOpenAIClientGetModel:
    @pytest.mark.asyncio
    async def test_text_model_supports_structured_output(self):
        client = _client((200, {"id": "gpt-6-luna", "object": "model"}))
        model = await client.get_model("gpt-6-luna", CREDENTIALS)
        assert model.id == "gpt-6-luna"
        assert model.capabilities == {AIModelCapability.STRUCTURED_OUTPUT}
        assert _sent(client)[1] == "https://api.openai.com/v1/models/gpt-6-luna"

    @pytest.mark.parametrize(
        "model_id",
        [
            "text-embedding-3-large",
            "whisper-1",
            "gpt-image-1",
            "gpt-6-realtime",
            "gpt-6-mini-transcribe",
            "gpt-6-audio-preview",
        ],
    )
    @pytest.mark.asyncio
    async def test_non_text_models_have_no_capabilities(self, model_id):
        client = _client((200, {"id": model_id, "object": "model"}))
        model = await client.get_model(model_id, CREDENTIALS)
        assert model.capabilities == set()

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        client = _client((404, {"error": {"message": "Not found"}}))
        assert await client.get_model("gpt-missing", CREDENTIALS) is None

    @pytest.mark.asyncio
    async def test_escapes_model_id(self):
        client = _client((404, {"error": {"message": "Not found"}}))
        await client.get_model("ft:gpt/x", CREDENTIALS)
        assert _sent(client)[1].endswith("/models/ft%3Agpt%2Fx")


class TestOpenAIClientGenerate:
    @pytest.mark.asyncio
    async def test_builds_responses_body(self):
        client = _client((200, _output(_text("{}"))))
        await client.generate(
            _request(
                instructions="Be precise",
                response_schema=AIJsonSchema(name="results", schema={"type": "object"}),
                reasoning_effort=AIReasoningEffort.NONE,
                max_output_tokens=200,
            ),
            CREDENTIALS,
        )
        method, url, kwargs = _sent(client)
        body = kwargs["json"]
        assert method == "POST"
        assert url == "https://api.openai.com/v1/responses"
        assert body == {
            "model": "gpt-6-luna",
            "input": [{"role": "user", "content": "hello"}],
            "store": False,
            "instructions": "Be precise",
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "results",
                    "strict": True,
                    "schema": {"type": "object"},
                }
            },
            "reasoning": {"effort": "none"},
            "max_output_tokens": 200,
        }

    @pytest.mark.asyncio
    async def test_sends_temperature_only_when_given(self):
        client = _client((200, _output(_text("{}"))))
        await client.generate(_request(temperature=Dezimal("0.2")), CREDENTIALS)
        assert _sent(client)[2]["json"]["temperature"] == 0.2

    @pytest.mark.asyncio
    async def test_maps_completed_output(self):
        client = _client(
            (
                200,
                _output(
                    _text('{"results": '),
                    _text("[]}"),
                    usage={"input_tokens": 12, "output_tokens": 4},
                ),
            )
        )
        generation = await client.generate(_request(), CREDENTIALS)
        assert generation.status == AIGenerationStatus.COMPLETED
        assert generation.text == '{"results": []}'
        assert generation.refusal is None
        assert generation.usage.input_tokens == 12
        assert generation.usage.output_tokens == 4

    @pytest.mark.asyncio
    async def test_maps_refusal(self):
        client = _client(
            (200, _output({"type": "refusal", "refusal": "I cannot help"}))
        )
        generation = await client.generate(_request(), CREDENTIALS)
        assert generation.status == AIGenerationStatus.REFUSED
        assert generation.refusal == "I cannot help"
        assert generation.text is None

    @pytest.mark.asyncio
    async def test_maps_incomplete_response(self):
        client = _client((200, _output(_text('{"res'), response_status="incomplete")))
        generation = await client.generate(_request(), CREDENTIALS)
        assert generation.status == AIGenerationStatus.INCOMPLETE

    @pytest.mark.asyncio
    async def test_rejects_upstream_provider(self):
        client = _client()
        with pytest.raises(AIProviderError) as error:
            await client.generate(_request(upstream_provider="azure"), CREDENTIALS)
        assert error.value.code == AIProviderErrorCode.UNSUPPORTED_OPERATION
        client._session.request.assert_not_called()


class TestOpenAIClientErrors:
    @pytest.mark.asyncio
    async def test_insufficient_quota_is_not_retried(self):
        client = _client((429, QUOTA_ERROR))
        with pytest.raises(AIProviderError) as error:
            await client.generate(_request(), CREDENTIALS)
        assert error.value.code == AIProviderErrorCode.INSUFFICIENT_FUNDS
        assert client._session.request.call_count == 1

    @pytest.mark.asyncio
    async def test_unauthorized_raises_invalid_credentials(self):
        client = _client((401, {"error": {"message": "Incorrect API key"}}))
        with pytest.raises(AIProviderError) as error:
            await client.generate(_request(), CREDENTIALS)
        assert error.value.code == AIProviderErrorCode.INVALID_CREDENTIALS

    @pytest.mark.asyncio
    async def test_bad_request_raises_unavailable(self):
        client = _client((400, {"error": {"message": "Unsupported parameter"}}))
        with pytest.raises(AIProviderError) as error:
            await client.generate(_request(), CREDENTIALS)
        assert error.value.code == AIProviderErrorCode.UNAVAILABLE

    @pytest.mark.asyncio
    async def test_retries_transient_errors(self):
        client = _client(
            (503, {"error": {"message": "Overloaded"}}),
            (429, {"error": {"message": "Rate limit", "code": "rate_limit_exceeded"}}),
            (200, _output(_text("{}"))),
        )
        generation = await client.generate(_request(), CREDENTIALS)
        assert generation.status == AIGenerationStatus.COMPLETED
        assert client._session.request.call_count == 3
