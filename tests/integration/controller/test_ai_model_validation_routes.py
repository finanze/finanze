from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio

from application.use_cases.validate_ai_model import ValidateAIModelImpl
from domain.external_integration import ExternalIntegrationId
from infrastructure.client.ai.openai.openai_client import OpenAIClient
from infrastructure.client.ai.openrouter.openrouter_client import OpenRouterClient
from infrastructure.client.http.http_response import HttpResponse
from infrastructure.controller.config import quart
from infrastructure.controller.exception_handler import register_exception_handlers
from infrastructure.controller.routes.validate_ai_model import validate_ai_model

URL = "/api/v1/ai/models/validate"
OPENROUTER_MODEL = {
    "data": {
        "name": "GPT Test",
        "architecture": {"output_modalities": ["text"]},
        "supported_parameters": ["structured_outputs", "temperature"],
    }
}
OPENROUTER_ENDPOINTS = {
    "data": {
        "endpoints": [
            {"tag": "azure", "supported_parameters": ["temperature"]},
            {"tag": "openai/flex", "supported_parameters": ["response_format"]},
        ]
    }
}


def _session(responses: dict) -> AsyncMock:
    async def request(method, url, **kwargs):
        for suffix, body in responses.items():
            if url.endswith(suffix):
                return HttpResponse(httpx.Response(200, json=body))
        return HttpResponse(httpx.Response(404, json={}))

    session = AsyncMock()
    session.request.side_effect = request
    return session


@pytest_asyncio.fixture
async def http(tmp_path):
    openrouter = OpenRouterClient()
    openrouter._session = _session(
        {
            "/model/openai/gpt-test": OPENROUTER_MODEL,
            "/models/openai/gpt-test/endpoints": OPENROUTER_ENDPOINTS,
        }
    )
    openai = OpenAIClient()
    openai._session = _session({"/models/gpt-6-luna": {"id": "gpt-6-luna"}})
    integration_port = AsyncMock()
    integration_port.get_payload = AsyncMock(return_value={"api_key": "k"})
    uc = ValidateAIModelImpl(
        integration_port,
        {
            ExternalIntegrationId.OPENROUTER: openrouter,
            ExternalIntegrationId.OPENAI: openai,
        },
    )

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    app = quart(static_dir)
    register_exception_handlers(app)

    @app.route(URL, methods=["POST"])
    async def validate_ai_model_route():
        return await validate_ai_model(uc)

    yield app.test_client()


@pytest.mark.asyncio
async def test_validates_openrouter_model_with_upstream(http):
    response = await http.post(
        URL,
        json={
            "provider": "OPENROUTER",
            "model": "openai/gpt-test",
            "task": "LABELING",
            "upstream_provider": "openai",
        },
    )
    assert response.status_code == 200
    assert await response.get_json() == {
        "valid": True,
        "name": "GPT Test",
        "capabilities": ["STRUCTURED_OUTPUT"],
        "upstream_provider": "openai/flex",
    }


@pytest.mark.asyncio
async def test_rejects_upstream_without_structured_output(http):
    response = await http.post(
        URL,
        json={
            "provider": "OPENROUTER",
            "model": "openai/gpt-test",
            "task": "LABELING",
            "upstream_provider": "azure",
        },
    )
    assert (await response.get_json())["valid"] is False


@pytest.mark.asyncio
async def test_validates_openai_model(http):
    response = await http.post(
        URL, json={"provider": "OPENAI", "model": "gpt-6-luna", "task": "LABELING"}
    )
    body = await response.get_json()
    assert body["valid"] is True
    assert "STRUCTURED_OUTPUT" in body["capabilities"]


@pytest.mark.asyncio
async def test_unknown_model_is_invalid(http):
    response = await http.post(
        URL, json={"provider": "OPENAI", "model": "missing", "task": "LABELING"}
    )
    assert response.status_code == 200
    assert (await response.get_json())["valid"] is False


@pytest.mark.parametrize(
    "body",
    [
        {"provider": "OPENAI", "model": "gpt-6-luna"},
        {"provider": "OPENAI", "model": "gpt-6-luna", "task": "UNKNOWN"},
        {"provider": "NOPE", "model": "gpt-6-luna", "task": "LABELING"},
    ],
)
@pytest.mark.asyncio
async def test_invalid_request(http, body):
    response = await http.post(URL, json=body)
    assert response.status_code == 400
    assert (await response.get_json())["code"] == "INVALID_REQUEST"


@pytest.mark.asyncio
async def test_unsupported_integration_returns_not_found(http):
    response = await http.post(
        URL, json={"provider": "ETHERSCAN", "model": "x", "task": "LABELING"}
    )
    assert response.status_code == 404
