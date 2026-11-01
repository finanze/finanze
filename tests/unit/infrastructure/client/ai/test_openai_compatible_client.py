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
    AIServerError,
    AIServerInfo,
    AIServerKind,
    AIServerModel,
)
from domain.dezimal import Dezimal
from domain.exception.exceptions import (
    AIProviderError,
    AIProviderErrorCode,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
)
from infrastructure.client.ai.openai_compatible.openai_compatible_client import (
    OpenAICompatibleClient,
)
from infrastructure.client.http.http_response import HttpResponse

CREDENTIALS = {"base_url": "http://localhost:1234", "api_key": "secret"}
SCHEMA = AIJsonSchema(name="results", schema={"type": "object"})
COMPLETION = {
    "choices": [
        {"message": {"role": "assistant", "content": "{}"}, "finish_reason": "stop"}
    ]
}


def _response(status: int, body=None, text: str = None) -> HttpResponse:
    if text is not None:
        return HttpResponse(httpx.Response(status, text=text))
    return HttpResponse(httpx.Response(status, json=body))


def _client(*responses) -> OpenAICompatibleClient:
    client = OpenAICompatibleClient()
    client.BACKOFF_SECONDS = 0
    client._session = AsyncMock()
    client._session.request.side_effect = [
        r if isinstance(r, (HttpResponse, Exception)) else _response(*r)
        for r in responses
    ]
    return client


def _sent(client: OpenAICompatibleClient, index: int = 0):
    call = client._session.request.call_args_list[index]
    return call.args[0], call.args[1], call.kwargs


def _request(**kwargs) -> AIGenerationRequest:
    return AIGenerationRequest(
        model="qwen3",
        messages=[AIMessage(role=AIMessageRole.USER, content="hello")],
        **kwargs,
    )


def test_features_include_model_listing():
    assert OpenAICompatibleClient().features() == {
        AIClientFeature.GENERATION,
        AIClientFeature.DECISIONS,
        AIClientFeature.MODEL_LISTING,
        AIClientFeature.CUSTOM_MODELS,
        AIClientFeature.SERVER_INFO,
    }


class TestSetup:
    @pytest.mark.asyncio
    async def test_accepts_model_list(self):
        client = _client((200, {"object": "list", "data": []}))
        await client.setup(CREDENTIALS)
        method, url, kwargs = _sent(client)
        assert method == "GET"
        assert url == "http://localhost:1234/v1/models"
        assert kwargs["headers"] == {"Authorization": "Bearer secret"}
        assert kwargs["timeout"] == OpenAICompatibleClient.SETUP_TIMEOUT_SECONDS

    @pytest.mark.asyncio
    async def test_api_key_is_optional(self):
        client = _client((200, {"data": []}))
        await client.setup({"base_url": "https://ai.example.com/api/v1"})
        method, url, kwargs = _sent(client)
        assert url == "https://ai.example.com/api/v1/models"
        assert kwargs["headers"] == {}

    @pytest.mark.parametrize("url", ["", "localhost:1234", "http://a:b@host"])
    @pytest.mark.asyncio
    async def test_invalid_url(self, url):
        client = _client()
        with pytest.raises(IntegrationSetupError) as error:
            await client.setup({"base_url": url})
        assert error.value.code == IntegrationSetupErrorCode.INVALID_URL
        client._session.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_transport_error_is_unreachable(self):
        client = _client(httpx.ConnectError("refused"))
        with pytest.raises(IntegrationSetupError) as error:
            await client.setup(CREDENTIALS)
        assert error.value.code == IntegrationSetupErrorCode.UNREACHABLE

    @pytest.mark.parametrize(
        "status, code",
        [
            (401, IntegrationSetupErrorCode.INVALID_CREDENTIALS),
            (403, IntegrationSetupErrorCode.INVALID_CREDENTIALS),
            (404, IntegrationSetupErrorCode.INVALID_URL),
            (405, IntegrationSetupErrorCode.INVALID_URL),
            (500, IntegrationSetupErrorCode.UNREACHABLE),
        ],
    )
    @pytest.mark.asyncio
    async def test_status_mapping(self, status, code):
        client = _client((status, {"error": {"message": "x"}}))
        with pytest.raises(IntegrationSetupError) as error:
            await client.setup(CREDENTIALS)
        assert error.value.code == code

    @pytest.mark.asyncio
    async def test_retries_unavailable_before_failing(self):
        unavailable = (503, {})
        client = _client(*[unavailable] * (OpenAICompatibleClient.MAX_RETRIES + 1))
        with pytest.raises(IntegrationSetupError) as error:
            await client.setup(CREDENTIALS)
        assert error.value.code == IntegrationSetupErrorCode.UNREACHABLE
        assert (
            client._session.request.call_count == OpenAICompatibleClient.MAX_RETRIES + 1
        )

    @pytest.mark.parametrize(
        "response",
        [
            _response(200, text="<html>Hello</html>"),
            _response(200, {"models": []}),
            _response(200, ["a"]),
        ],
    )
    @pytest.mark.asyncio
    async def test_non_openai_response_is_invalid_url(self, response):
        client = _client(response)
        with pytest.raises(IntegrationSetupError) as error:
            await client.setup(CREDENTIALS)
        assert error.value.code == IntegrationSetupErrorCode.INVALID_URL


class TestListModels:
    @pytest.mark.asyncio
    async def test_lists_sorted_models_with_capabilities(self):
        client = _client(
            (
                200,
                {
                    "data": [
                        {"id": "zeta"},
                        {
                            "id": "laya",
                            "name": "Laya",
                            "architecture": {"output_modalities": ["decisions"]},
                        },
                        {
                            "id": "embed",
                            "architecture": {"output_modalities": ["embeddings"]},
                        },
                        {"name": "no id"},
                        "invalid",
                    ]
                },
            )
        )
        models = await client.list_models(CREDENTIALS)
        assert [m.id for m in models] == ["embed", "laya", "zeta"]
        assert models[0].capabilities == set()
        assert models[1].name == "Laya"
        assert models[1].capabilities == {AIModelCapability.DECISIONS}
        assert models[2].capabilities == {
            AIModelCapability.STRUCTURED_OUTPUT,
            AIModelCapability.TEMPERATURE,
        }

    @pytest.mark.asyncio
    async def test_get_model(self):
        client = _client((200, {"data": [{"id": "a"}]}), (200, {"data": []}))
        assert (await client.get_model("a", CREDENTIALS)).id == "a"
        assert await client.get_model("a", CREDENTIALS) is None

    @pytest.mark.asyncio
    async def test_transport_error_is_unavailable(self):
        client = _client(httpx.ReadTimeout("slow"))
        with pytest.raises(AIProviderError) as error:
            await client.list_models(CREDENTIALS)
        assert error.value.code == AIProviderErrorCode.UNAVAILABLE

    @pytest.mark.asyncio
    async def test_invalid_stored_url_is_unavailable(self):
        client = _client()
        with pytest.raises(AIProviderError) as error:
            await client.list_models({"base_url": "nope"})
        assert error.value.code == AIProviderErrorCode.UNAVAILABLE


class TestGenerate:
    @pytest.mark.asyncio
    async def test_builds_chat_completions_body(self):
        client = _client((200, COMPLETION))
        generation = await client.generate(
            _request(
                instructions="Be precise",
                response_schema=SCHEMA,
                temperature=Dezimal("0.2"),
                reasoning_effort=AIReasoningEffort.NONE,
                max_output_tokens=100,
            ),
            CREDENTIALS,
        )
        assert generation.status == AIGenerationStatus.COMPLETED
        method, url, kwargs = _sent(client)
        assert method == "POST"
        assert url == "http://localhost:1234/v1/chat/completions"
        assert kwargs["timeout"] == OpenAICompatibleClient.REQUEST_TIMEOUT_SECONDS
        assert kwargs["json"] == {
            "model": "qwen3",
            "messages": [
                {"role": "system", "content": "Be precise"},
                {"role": "user", "content": "hello"},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "results",
                    "strict": True,
                    "schema": {"type": "object"},
                },
            },
            "temperature": 0.2,
            "reasoning_effort": "none",
            "max_tokens": 100,
        }

    @pytest.mark.asyncio
    async def test_without_schema_has_no_response_format(self):
        client = _client((200, COMPLETION))
        await client.generate(_request(), CREDENTIALS)
        assert "response_format" not in _sent(client)[2]["json"]

    @pytest.mark.parametrize("status", [400, 422])
    @pytest.mark.asyncio
    async def test_falls_back_to_json_object_and_remembers(self, status):
        client = _client(
            (status, {"error": {"message": "json_schema not supported"}}),
            (200, COMPLETION),
            (200, COMPLETION),
        )
        await client.generate(_request(response_schema=SCHEMA), CREDENTIALS)
        fallback = _sent(client, 1)[2]["json"]
        assert fallback["response_format"] == {"type": "json_object"}
        assert fallback["messages"][0]["role"] == "system"
        assert '{"type": "object"}' in fallback["messages"][0]["content"]
        assert fallback["messages"][1] == {"role": "user", "content": "hello"}

        await client.generate(
            _request(instructions="Be precise", response_schema=SCHEMA), CREDENTIALS
        )
        assert client._session.request.call_count == 3
        cached = _sent(client, 2)[2]["json"]
        assert cached["response_format"] == {"type": "json_object"}
        assert cached["messages"][0]["content"].startswith("Be precise\n\n")

    @pytest.mark.asyncio
    async def test_fallback_is_per_server(self):
        client = _client(
            (400, {}),
            (200, COMPLETION),
            (200, COMPLETION),
        )
        await client.generate(_request(response_schema=SCHEMA), CREDENTIALS)
        await client.generate(
            _request(response_schema=SCHEMA), {"base_url": "http://other:1234"}
        )
        assert _sent(client, 2)[2]["json"]["response_format"]["type"] == "json_schema"

    @pytest.mark.asyncio
    async def test_server_error(self):
        client = _client((500, {"error": {"message": "boom"}}))
        with pytest.raises(AIProviderError) as error:
            await client.generate(_request(response_schema=SCHEMA), CREDENTIALS)
        assert error.value.code == AIProviderErrorCode.UNAVAILABLE

    @pytest.mark.asyncio
    async def test_invalid_credentials(self):
        client = _client((401, {}))
        with pytest.raises(AIProviderError) as error:
            await client.generate(_request(), CREDENTIALS)
        assert error.value.code == AIProviderErrorCode.INVALID_CREDENTIALS


class TestDecide:
    @pytest.mark.asyncio
    async def test_posts_to_decisions_endpoint(self):
        client = _client(
            (200, {"answers": {"m1": {"choice": "food", "confidence": 0.9}}})
        )
        result = await client.decide(
            AIDecisionRequest(
                model="laya",
                state={"categories": {"food": "Food"}},
                questions=[
                    AIChoiceQuestion(id="m1", instructions="Pick", options=["food"])
                ],
            ),
            CREDENTIALS,
        )
        method, url, kwargs = _sent(client)
        assert method == "POST"
        assert url == "http://localhost:1234/v1/systemone"
        assert kwargs["json"]["model"] == "laya"
        assert result.answers["m1"].choice == "food"
        assert result.answers["m1"].confidence == Dezimal("0.9")


ROOT = "http://localhost:1234"
MODELS_URL = f"{ROOT}/v1/models"


def _server(routes: dict) -> OpenAICompatibleClient:
    async def request(method, url, **kwargs):
        route = routes.get(url)
        if isinstance(route, Exception):
            raise route
        if route is None:
            return _response(404, {})
        if isinstance(route, tuple):
            return _response(*route)
        return _response(200, route)

    client = OpenAICompatibleClient()
    client._session = AsyncMock()
    client._session.request.side_effect = request
    return client


def _models(*entries) -> dict:
    return {"object": "list", "data": list(entries)}


class TestServerInfo:
    @pytest.mark.asyncio
    async def test_describes_ollama(self):
        client = _server(
            {
                MODELS_URL: _models(
                    {"id": "qwen3:8b", "owned_by": "library"},
                    {"id": "llama3.2:latest", "owned_by": "library"},
                ),
                f"{ROOT}/api/version": {"version": "0.12.3"},
                f"{ROOT}/api/ps": {
                    "models": [
                        {
                            "name": "qwen3:8b",
                            "model": "qwen3:8b",
                            "size": 6654289920,
                            "context_length": 8192,
                        }
                    ]
                },
            }
        )
        info = await client.get_server_info(CREDENTIALS)
        assert info.latency_ms is not None and info.latency_ms >= 0
        info.latency_ms = None
        assert info == AIServerInfo(
            url="http://localhost:1234/v1",
            api_key_set=True,
            reachable=True,
            kind=AIServerKind.OLLAMA,
            version="0.12.3",
            models=[
                AIServerModel(id="llama3.2:latest", loaded=False),
                AIServerModel(
                    id="qwen3:8b", loaded=True, size=6654289920, context_length=8192
                ),
            ],
        )

    @pytest.mark.asyncio
    async def test_detects_namespaced_ollama_by_version_probe(self):
        client = _server(
            {
                MODELS_URL: _models(
                    {"id": "hf.co/bartowski/qwen", "owned_by": "hf.co"}
                ),
                f"{ROOT}/api/version": {"version": "0.12.3"},
                f"{ROOT}/api/ps": {"models": []},
            }
        )
        info = await client.get_server_info(CREDENTIALS)
        assert info.kind == AIServerKind.OLLAMA
        assert info.version == "0.12.3"
        assert info.models == [AIServerModel(id="hf.co/bartowski/qwen", loaded=False)]

    @pytest.mark.asyncio
    async def test_describes_lm_studio(self):
        client = _server(
            {
                MODELS_URL: _models(
                    {"id": "google/gemma", "owned_by": "organization_owner"},
                    {
                        "id": "jev/laya",
                        "owned_by": "organization_owner",
                        "architecture": {"output_modalities": ["decisions"]},
                    },
                ),
                f"{ROOT}/api/v1/models": {
                    "models": [
                        {
                            "key": "google/gemma",
                            "size_bytes": 17990911801,
                            "max_context_length": 262144,
                            "loaded_instances": [
                                {
                                    "id": "google/gemma",
                                    "config": {"context_length": 4096},
                                }
                            ],
                        },
                        {
                            "key": "jev/laya",
                            "size_bytes": 1000,
                            "max_context_length": 2048,
                            "loaded_instances": [],
                        },
                    ]
                },
            }
        )
        info = await client.get_server_info(CREDENTIALS)
        assert info.kind == AIServerKind.LM_STUDIO
        assert info.version is None
        assert info.models == [
            AIServerModel(
                id="google/gemma", loaded=True, size=17990911801, context_length=4096
            ),
            AIServerModel(
                id="jev/laya",
                decisions=True,
                loaded=False,
                size=1000,
                context_length=2048,
            ),
        ]

    @pytest.mark.asyncio
    async def test_describes_single_model_llama_cpp(self):
        client = _server(
            {
                MODELS_URL: _models(
                    {
                        "id": "qwen.gguf",
                        "owned_by": "llamacpp",
                        "meta": {"n_ctx_train": 131072, "size": 4920000000},
                    }
                ),
                f"{ROOT}/props": {
                    "build_info": "b6643-2a9ea2020",
                    "default_generation_settings": {"n_ctx": 8192},
                },
            }
        )
        info = await client.get_server_info(CREDENTIALS)
        assert info.kind == AIServerKind.LLAMA_CPP
        assert info.version == "b6643-2a9ea2020"
        assert info.models == [
            AIServerModel(
                id="qwen.gguf", loaded=True, size=4920000000, context_length=8192
            )
        ]

    @pytest.mark.asyncio
    async def test_describes_llama_cpp_router(self):
        client = _server(
            {
                MODELS_URL: _models(
                    {"id": "a", "status": {"value": "loaded"}},
                    {"id": "b", "status": {"value": "unloaded"}},
                ),
                f"{ROOT}/props": (400, {"error": "model required"}),
            }
        )
        info = await client.get_server_info(CREDENTIALS)
        assert info.kind == AIServerKind.LLAMA_CPP
        assert info.version is None
        assert info.models == [
            AIServerModel(id="a", loaded=True),
            AIServerModel(id="b", loaded=False),
        ]

    @pytest.mark.asyncio
    async def test_describes_vllm(self):
        client = _server(
            {
                MODELS_URL: _models(
                    {"id": "Qwen/Qwen3-8B", "owned_by": "vllm", "max_model_len": 32768}
                ),
                f"{ROOT}/version": {"version": "0.11.0"},
            }
        )
        info = await client.get_server_info(CREDENTIALS)
        assert info.kind == AIServerKind.VLLM
        assert info.version == "0.11.0"
        assert info.models == [
            AIServerModel(id="Qwen/Qwen3-8B", loaded=True, context_length=32768)
        ]

    @pytest.mark.asyncio
    async def test_unknown_server_keeps_generic_details(self):
        client = _server({MODELS_URL: _models({"id": "gpt-x", "owned_by": "acme"})})
        info = await client.get_server_info(CREDENTIALS)
        assert info.reachable is True
        assert info.error is None
        assert info.kind is None
        assert info.version is None
        assert info.models == [AIServerModel(id="gpt-x")]

    @pytest.mark.asyncio
    async def test_failing_probes_are_ignored(self):
        client = _server(
            {
                MODELS_URL: _models({"id": "qwen3:8b", "owned_by": "library"}),
                f"{ROOT}/api/version": httpx.ConnectError("down"),
                f"{ROOT}/api/ps": (200, None, "not json"),
            }
        )
        info = await client.get_server_info(CREDENTIALS)
        assert info.kind == AIServerKind.OLLAMA
        assert info.version is None
        assert info.models == [AIServerModel(id="qwen3:8b")]

    @pytest.mark.asyncio
    async def test_unreachable_server(self):
        client = _server({MODELS_URL: httpx.ConnectError("refused")})
        info = await client.get_server_info(CREDENTIALS)
        assert info == AIServerInfo(
            url="http://localhost:1234/v1",
            api_key_set=True,
            reachable=False,
            error=AIServerError.UNREACHABLE,
        )

    @pytest.mark.parametrize(
        "route,error",
        [
            ((401, {}), AIServerError.UNAUTHORIZED),
            ((403, {}), AIServerError.UNAUTHORIZED),
            ((404, {}), AIServerError.NOT_FOUND),
            ((503, {}), AIServerError.SERVER_ERROR),
            ((200, None, "<html></html>"), AIServerError.INVALID_RESPONSE),
            ((200, {"models": []}), AIServerError.INVALID_RESPONSE),
        ],
    )
    @pytest.mark.asyncio
    async def test_maps_model_listing_errors(self, route, error):
        client = _server({MODELS_URL: route})
        info = await client.get_server_info(CREDENTIALS)
        assert info.reachable is True
        assert info.error == error
        assert info.latency_ms is not None
        assert info.models == []
        assert client._session.request.call_count == 1

    @pytest.mark.asyncio
    async def test_without_api_key(self):
        client = _server({MODELS_URL: _models()})
        info = await client.get_server_info({"base_url": "http://localhost:1234/v1/"})
        assert info.api_key_set is False
        assert info.url == "http://localhost:1234/v1"
        assert client._session.request.call_args_list[0].kwargs["headers"] == {}
