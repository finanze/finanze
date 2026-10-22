from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio

from application.use_cases.get_ai_server_info import GetAIServerInfoImpl
from domain.external_integration import ExternalIntegrationId
from infrastructure.client.ai.openai.openai_client import OpenAIClient
from infrastructure.client.ai.openai_compatible.openai_compatible_client import (
    OpenAICompatibleClient,
)
from infrastructure.client.http.http_response import HttpResponse
from infrastructure.controller.config import quart
from infrastructure.controller.exception_handler import register_exception_handlers
from infrastructure.controller.routes.get_ai_server_info import get_ai_server_info

URL = "/api/v1/ai/providers/<provider_id>/server"
SERVER_ROUTES = {
    "http://vllm.local:8000/v1/models": {
        "data": [
            {
                "id": "Qwen/Qwen3-8B",
                "owned_by": "vllm",
                "max_model_len": 32768,
                "architecture": {"output_modalities": ["text"]},
            }
        ]
    },
    "http://vllm.local:8000/version": {"version": "0.11.0"},
}


def _session(routes: dict) -> AsyncMock:
    async def request(method, url, **kwargs):
        if url in routes:
            return HttpResponse(httpx.Response(200, json=routes[url]))
        return HttpResponse(httpx.Response(404, json={}))

    session = AsyncMock()
    session.request.side_effect = request
    return session


def _app(tmp_path, payload):
    compatible = OpenAICompatibleClient()
    compatible._session = _session(SERVER_ROUTES)
    integration_port = AsyncMock()
    integration_port.get_payload = AsyncMock(return_value=payload)
    uc = GetAIServerInfoImpl(
        integration_port,
        {
            ExternalIntegrationId.OPENAI_COMPATIBLE: compatible,
            ExternalIntegrationId.OPENAI: OpenAIClient(),
        },
    )

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    app = quart(static_dir)
    register_exception_handlers(app)

    @app.route(URL, methods=["GET"])
    async def get_ai_server_info_route(provider_id: str):
        return await get_ai_server_info(uc, provider_id)

    return app.test_client()


@pytest_asyncio.fixture
async def http(tmp_path):
    yield _app(tmp_path, {"base_url": "http://vllm.local:8000", "api_key": "k"})


@pytest.mark.asyncio
async def test_returns_server_details(http):
    response = await http.get("/api/v1/ai/providers/OPENAI_COMPATIBLE/server")
    assert response.status_code == 200
    body = await response.get_json()
    assert body["latency_ms"] >= 0
    body.pop("latency_ms")
    assert body == {
        "url": "http://vllm.local:8000/v1",
        "api_key_set": True,
        "reachable": True,
        "error": None,
        "kind": "VLLM",
        "version": "0.11.0",
        "models": [
            {
                "id": "Qwen/Qwen3-8B",
                "decisions": False,
                "loaded": True,
                "size": None,
                "context_length": 32768,
            }
        ],
    }


@pytest.mark.parametrize("provider_id", ["OPENAI", "NOPE"])
@pytest.mark.asyncio
async def test_unsupported_provider_returns_not_found(http, provider_id):
    response = await http.get(f"/api/v1/ai/providers/{provider_id}/server")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_disconnected_integration_requires_setup(tmp_path):
    http = _app(tmp_path, None)
    response = await http.get("/api/v1/ai/providers/OPENAI_COMPATIBLE/server")
    assert response.status_code == 409
    assert (await response.get_json())["code"] == "REQUIRED_INTEGRATION"
