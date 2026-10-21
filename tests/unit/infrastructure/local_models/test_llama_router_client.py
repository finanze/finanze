from unittest.mock import AsyncMock

import httpx
import pytest
from domain.exception.exceptions import LocalModelError, LocalModelErrorCode
from domain.local_model import (
    LocalModelState,
    LocalRouterConnection,
    LocalRuntimeMode,
    LocalRuntimeSource,
)
from infrastructure.client.http.http_response import HttpResponse
from infrastructure.local_models.llama_router_client import (
    LlamaRouterClient,
    parse_router_model,
)

CONNECTION = LocalRouterConnection(
    base_url="http://127.0.0.1:8080",
    api_key="secret",
    mode=LocalRuntimeMode.BUILT_IN,
    source=LocalRuntimeSource.BUILT_IN,
)
OPEN_CONNECTION = LocalRouterConnection(
    base_url="http://server:8080",
    mode=LocalRuntimeMode.EXTERNAL,
    source=LocalRuntimeSource.PAYLOAD,
)


class FakeProgress:
    def __init__(self, progress: dict | None = None):
        self.progress = progress or {}
        self.watched: list[tuple[LocalRouterConnection, set[str]]] = []

    def watch(self, connection, downloading):
        self.watched.append((connection, downloading))

    def get(self, model_id):
        return self.progress.get(model_id)


def _response(status: int, body=None, text: str = None) -> HttpResponse:
    if text is not None:
        return HttpResponse(httpx.Response(status, text=text))
    return HttpResponse(httpx.Response(status, json=body))


def _client(*responses, progress: FakeProgress | None = None) -> LlamaRouterClient:
    client = LlamaRouterClient(progress or FakeProgress())
    client._session = AsyncMock()
    client._session.request.side_effect = [
        r if isinstance(r, (HttpResponse, Exception)) else _response(*r)
        for r in responses
    ]
    return client


def _sent(client: LlamaRouterClient, index: int = 0):
    call = client._session.request.call_args_list[index]
    return call.args[0], call.args[1], call.kwargs


def _entry(model_id: str, value: str = "unloaded", **kwargs) -> dict:
    return {"id": model_id, "status": {"value": value}, **kwargs}


class TestParseRouterModel:
    @pytest.mark.parametrize(
        "value, state",
        [
            ("unloaded", LocalModelState.UNLOADED),
            ("downloaded", LocalModelState.UNLOADED),
            ("loading", LocalModelState.LOADING),
            ("loaded", LocalModelState.LOADED),
            ("sleeping", LocalModelState.SLEEPING),
            ("downloading", LocalModelState.DOWNLOADING),
            ("unknown", LocalModelState.UNLOADED),
        ],
    )
    def test_states(self, value, state):
        assert parse_router_model(_entry("a", value)).state == state

    def test_failed_flag_wins(self):
        entry = {"id": "a", "status": {"value": "unloaded", "failed": True}}
        assert parse_router_model(entry).state == LocalModelState.FAILED

    def test_metadata(self):
        model = parse_router_model(
            _entry(
                "org/laya-GGUF:Q8_0",
                meta={"size": "449397600"},
                architecture={"output_modalities": ["decisions"]},
                can_remove=True,
            )
        )
        assert model.id == "org/laya-GGUF:Q8_0"
        assert model.size == 449397600
        assert model.decisions is True
        assert model.removable is True

    def test_tolerates_malformed_fields(self):
        model = parse_router_model(
            {
                "id": "a",
                "status": "loaded",
                "meta": [],
                "architecture": "x",
                "can_remove": "yes",
            }
        )
        assert model.state == LocalModelState.UNLOADED
        assert model.size is None
        assert model.decisions is False
        assert model.removable is None

    def test_without_id(self):
        assert parse_router_model({"status": {"value": "loaded"}}) is None


class TestProbe:
    @pytest.mark.parametrize("health_status", [200, 503])
    @pytest.mark.asyncio
    async def test_accepts_router(self, health_status):
        client = _client((health_status, {}), (200, {"data": [_entry("a")]}))
        await client.probe(CONNECTION)
        method, url, kwargs = _sent(client)
        assert (method, url) == ("GET", "http://127.0.0.1:8080/health")
        assert kwargs["headers"] == {"Authorization": "Bearer secret"}
        assert _sent(client, 1)[1] == "http://127.0.0.1:8080/models"

    @pytest.mark.asyncio
    async def test_no_auth_header_without_key(self):
        client = _client((200, {}), (200, {"data": []}))
        await client.probe(OPEN_CONNECTION)
        assert _sent(client)[2]["headers"] == {}

    @pytest.mark.asyncio
    async def test_unreachable(self):
        client = _client(httpx.ConnectError("refused"))
        with pytest.raises(LocalModelError) as error:
            await client.probe(CONNECTION)
        assert error.value.code == LocalModelErrorCode.UNREACHABLE

    @pytest.mark.parametrize(
        "responses, code",
        [
            ([(404, {})], LocalModelErrorCode.NOT_A_MODEL_ROUTER),
            ([(500, {})], LocalModelErrorCode.UNREACHABLE),
            ([(200, {}), (401, {})], LocalModelErrorCode.UNAUTHORIZED),
            ([(200, {}), (403, {})], LocalModelErrorCode.UNAUTHORIZED),
            ([(200, {}), (404, {})], LocalModelErrorCode.NOT_A_MODEL_ROUTER),
            (
                [(200, {}), _response(200, text="<html/>")],
                LocalModelErrorCode.NOT_A_MODEL_ROUTER,
            ),
            (
                [(200, {}), (200, {"object": "list"})],
                LocalModelErrorCode.NOT_A_MODEL_ROUTER,
            ),
            (
                [(200, {}), (200, {"data": [{"id": "a", "object": "model"}]})],
                LocalModelErrorCode.NOT_A_MODEL_ROUTER,
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_rejections(self, responses, code):
        client = _client(*responses)
        with pytest.raises(LocalModelError) as error:
            await client.probe(CONNECTION)
        assert error.value.code == code


class TestIsHealthy:
    @pytest.mark.asyncio
    async def test_healthy(self):
        assert await _client((200, {})).is_healthy(CONNECTION)

    @pytest.mark.asyncio
    async def test_loading(self):
        assert not await _client((503, {})).is_healthy(CONNECTION)

    @pytest.mark.asyncio
    async def test_unreachable(self):
        assert not await _client(httpx.ConnectError("x")).is_healthy(CONNECTION)


class TestListModels:
    @pytest.mark.asyncio
    async def test_parses_models_and_watches_downloads(self):
        progress = FakeProgress({"org/b-GGUF:Q4_K_M": (100, 400)})
        client = _client(
            (
                200,
                {
                    "data": [
                        _entry("org/a-GGUF:Q4_K_M", "loaded", meta={"size": 10}),
                        _entry("org/b-GGUF:Q4_K_M", "downloading"),
                        "invalid",
                        {"status": {"value": "loaded"}},
                    ]
                },
            ),
            progress=progress,
        )
        models = await client.list_models(CONNECTION)
        assert [m.id for m in models] == ["org/a-GGUF:Q4_K_M", "org/b-GGUF:Q4_K_M"]
        assert models[0].downloaded is None
        assert models[0].size == 10
        assert models[1].downloaded == 100
        assert models[1].size == 400
        assert progress.watched == [(CONNECTION, {"org/b-GGUF:Q4_K_M"})]
        assert _sent(client)[2]["params"] is None

    @pytest.mark.asyncio
    async def test_unknown_total_keeps_router_size(self):
        progress = FakeProgress({"a:Q4": (5, None)})
        client = _client(
            (200, {"data": [_entry("a:Q4", "downloading", meta={"size": 50})]}),
            progress=progress,
        )
        models = await client.list_models(CONNECTION)
        assert models[0].downloaded == 5
        assert models[0].size == 50

    @pytest.mark.asyncio
    async def test_reload(self):
        client = _client((200, {"data": []}))
        await client.list_models(CONNECTION, reload=True)
        assert _sent(client)[2]["params"] == {"reload": "1"}

    @pytest.mark.parametrize(
        "status, code",
        [
            (401, LocalModelErrorCode.UNAUTHORIZED),
            (404, LocalModelErrorCode.MODEL_NOT_FOUND),
            (500, LocalModelErrorCode.SERVER_ERROR),
        ],
    )
    @pytest.mark.asyncio
    async def test_errors(self, status, code):
        client = _client((status, {"error": {"message": "nope"}}))
        with pytest.raises(LocalModelError) as error:
            await client.list_models(CONNECTION)
        assert error.value.code == code
        assert error.value.details == "nope"

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        client = _client(_response(200, text="oops"))
        with pytest.raises(LocalModelError) as error:
            await client.list_models(CONNECTION)
        assert error.value.code == LocalModelErrorCode.SERVER_ERROR


class TestModelOperations:
    @pytest.mark.asyncio
    async def test_download(self):
        client = _client((200, {"success": True}))
        await client.download(CONNECTION, "org/a-GGUF:Q4_K_M")
        method, url, kwargs = _sent(client)
        assert (method, url) == ("POST", "http://127.0.0.1:8080/models")
        assert kwargs["json"] == {"model": "org/a-GGUF:Q4_K_M", "sidecars": []}
        assert kwargs["timeout"] == LlamaRouterClient.DOWNLOAD_TIMEOUT_SECONDS

    @pytest.mark.asyncio
    async def test_download_rejected(self):
        client = _client((400, {"error": {"message": "file not found"}}))
        with pytest.raises(LocalModelError) as error:
            await client.download(CONNECTION, "org/a-GGUF:Q4_K_M")
        assert error.value.code == LocalModelErrorCode.DOWNLOAD_FAILED
        assert error.value.details == "file not found"

    @pytest.mark.asyncio
    async def test_delete(self):
        client = _client((200, {"success": True}))
        await client.delete(CONNECTION, "org/a-GGUF:Q4_K_M")
        method, url, kwargs = _sent(client)
        assert (method, url) == ("DELETE", "http://127.0.0.1:8080/models")
        assert kwargs["params"] == {"model": "org/a-GGUF:Q4_K_M"}

    @pytest.mark.asyncio
    async def test_delete_rejected(self):
        client = _client((400, {"error": {"message": "model is loaded"}}))
        with pytest.raises(LocalModelError) as error:
            await client.delete(CONNECTION, "a:Q4")
        assert error.value.code == LocalModelErrorCode.NOT_DELETABLE

    @pytest.mark.asyncio
    async def test_delete_missing(self):
        client = _client((404, {}))
        with pytest.raises(LocalModelError) as error:
            await client.delete(CONNECTION, "a:Q4")
        assert error.value.code == LocalModelErrorCode.MODEL_NOT_FOUND

    @pytest.mark.asyncio
    async def test_load_and_unload(self):
        client = _client((200, {"success": True}), (200, {"success": True}))
        await client.load(CONNECTION, "a:Q4")
        await client.unload(CONNECTION, "a:Q4")
        assert _sent(client)[1] == "http://127.0.0.1:8080/models/load"
        assert _sent(client)[2]["json"] == {"model": "a:Q4"}
        assert _sent(client, 1)[1] == "http://127.0.0.1:8080/models/unload"
