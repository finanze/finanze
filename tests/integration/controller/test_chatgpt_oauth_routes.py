import sqlite3
import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
import pytest_asyncio
from application.use_cases.complete_external_integration_connection import (
    CompleteExternalIntegrationConnectionImpl,
)
from application.use_cases.connect_external_integration import (
    ConnectExternalIntegrationImpl,
)
from application.use_cases.disconnect_external_integration import (
    DisconnectExternalIntegrationImpl,
)
from application.use_cases.forward_integration_oauth_callback import (
    ForwardIntegrationOAuthCallbackImpl,
)
from application.use_cases.get_external_integrations import (
    GetExternalIntegrationsImpl,
)
from application.use_cases.get_external_labeling_models import (
    GetExternalLabelingModelsImpl,
)
from cryptography.hazmat.primitives.asymmetric import rsa
from dateutil.tz import tzlocal
from domain.data_init import DatasourceInitContext
from domain.external_integration import ExternalIntegrationId
from infrastructure.client.ai.chatgpt.chatgpt_client import ChatGPTClient
from infrastructure.client.ai.chatgpt.chatgpt_oauth import (
    DISCOVERY_URL,
    ISSUER,
    JWKS_URL,
    TOKEN_URL,
    ChatGPTOAuth,
)
from infrastructure.client.http.http_response import HttpResponse
from infrastructure.controller.config import quart
from infrastructure.controller.exception_handler import register_exception_handlers
from infrastructure.controller.routes.complete_external_integration_connection import (
    complete_external_integration_connection,
)
from infrastructure.controller.routes.connect_external_integration import (
    connect_external_integration,
)
from infrastructure.controller.routes.disconnect_external_integration import (
    disconnect_external_integration,
)
from infrastructure.controller.routes.forward_integration_oauth_callback import (
    forward_integration_oauth_callback,
)
from infrastructure.controller.routes.get_external_integrations import (
    get_external_integrations,
)
from infrastructure.controller.routes.get_external_labeling_models import (
    get_external_labeling_models,
)
from infrastructure.labeling.ai_labeling_provider import AILabelingProvider
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import versions
from infrastructure.repository.external_integration.external_integration_repository import (
    ExternalIntegrationRepository,
)
from infrastructure.repository.host_identity.host_identity_repository import (
    HostIdentityRepository,
)
from jwt.algorithms import RSAAlgorithm

CHATGPT = ExternalIntegrationId.CHATGPT
PORT = 7592
ISSUED = "oaiapp_issued"
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=tzlocal())
WEB_COMPLETION = (
    "http://localhost:8080/?integration_oauth=CHATGPT"
    "#/entities?tab=providers&focus=CHATGPT"
)
MOBILE_CALLBACK = "http://127.0.0.1:53123/auth/callback"
REVOCATION_URL = "https://auth.openai.com/oauth/revoke"
PLAN_SCOPES = (
    "chatgpt.tokens.use.direct email offline_access openid profile resource.invoke"
)
SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
JWKS = {
    "keys": [
        {
            **RSAAlgorithm.to_jwk(SIGNING_KEY.public_key(), as_dict=True),
            "kid": "key",
            "alg": "RS256",
        }
    ]
}
MODELS = {
    "models": [
        {"slug": "gpt-6-sol", "display_name": "GPT-6 Sol", "visibility": "list"},
        {"slug": "hidden", "display_name": "Hidden", "visibility": "hide"},
    ]
}


def _id_token(nonce: str) -> str:
    issued_at = int(time.time())
    return jwt.encode(
        {
            "iss": ISSUER,
            "aud": ISSUED,
            "sub": "user-subject",
            "email": "user@example.com",
            "nonce": nonce,
            "iat": issued_at,
            "exp": issued_at + 3600,
        },
        SIGNING_KEY,
        algorithm="RS256",
        headers={"kid": "key"},
    )


def _tokens(nonce: str | None, access: str, refresh: str) -> dict:
    body = {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": PLAN_SCOPES,
    }
    if nonce:
        body["id_token"] = _id_token(nonce)
    return body


class WallClock:
    def __init__(self):
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


class FakeOpenAI:
    def __init__(self):
        self.token_responses: list[tuple[int, dict]] = []
        self.token_forms: list[dict] = []
        self.revocations: list[dict] = []
        self.api_tokens: list[str] = []

    async def post(self, url, **kwargs):
        if url == TOKEN_URL:
            self.token_forms.append(kwargs["data"])
            status, body = self.token_responses.pop(0)
            return HttpResponse(httpx.Response(status, json=body))
        assert url == REVOCATION_URL
        self.revocations.append(kwargs["data"])
        return HttpResponse(httpx.Response(200))

    async def get(self, url, **kwargs):
        if url == JWKS_URL:
            return HttpResponse(httpx.Response(200, json=JWKS))
        assert url == DISCOVERY_URL
        return HttpResponse(
            httpx.Response(200, json={"revocation_endpoint": REVOCATION_URL})
        )

    async def request(self, method, url, headers=None, **kwargs):
        assert (method, url) == ("GET", "https://api.openai.com/v1/models")
        self.api_tokens.append(headers["Authorization"])
        return HttpResponse(httpx.Response(200, json=MODELS))


@pytest_asyncio.fixture
async def ctx(tmp_path):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    client = DBClient(connection)
    await DatabaseUpgrader(
        client, versions, DatasourceInitContext(config=AsyncMock())
    ).upgrade()
    repository = ExternalIntegrationRepository(client)
    host_identity = HostIdentityRepository(client)

    openai = FakeOpenAI()
    wall = WallClock()
    chatgpt = ChatGPTClient(
        ChatGPTOAuth(host_identity, PORT, session=openai, now=wall),
        repository,
        now=wall,
    )
    chatgpt._session = openai
    integrations = {CHATGPT: chatgpt}

    get_uc = GetExternalIntegrationsImpl(repository, integrations)
    connect_uc = ConnectExternalIntegrationImpl(repository, integrations)
    complete_uc = CompleteExternalIntegrationConnectionImpl(repository, integrations)
    disconnect_uc = DisconnectExternalIntegrationImpl(repository, integrations)
    forward_uc = ForwardIntegrationOAuthCallbackImpl(integrations)
    models_uc = GetExternalLabelingModelsImpl(
        repository, {CHATGPT: AILabelingProvider(chatgpt, [])}
    )

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    app = quart(static_dir)
    register_exception_handlers(app)

    @app.route("/api/v1/integrations", methods=["GET"])
    async def get_integrations_route():
        return await get_external_integrations(get_uc)

    @app.route("/api/v1/integrations/<integration_id>", methods=["POST"])
    async def connect_route(integration_id: str):
        return await connect_external_integration(connect_uc, integration_id)

    @app.route("/api/v1/integrations/<integration_id>", methods=["DELETE"])
    async def disconnect_route(integration_id: str):
        return await disconnect_external_integration(disconnect_uc, integration_id)

    @app.route("/api/v1/integrations/<integration_id>/oauth/complete", methods=["POST"])
    async def complete_route(integration_id: str):
        return await complete_external_integration_connection(
            complete_uc, integration_id
        )

    @app.route("/auth/callback", methods=["GET"])
    async def forward_route():
        return await forward_integration_oauth_callback(forward_uc)

    @app.route(
        "/api/v1/labeling/external/providers/<provider_id>/models", methods=["GET"]
    )
    async def models_route(provider_id: str):
        return await get_external_labeling_models(models_uc, provider_id)

    yield SimpleNamespace(
        http=app.test_client(),
        repository=repository,
        host_identity=host_identity,
        openai=openai,
        wall=wall,
    )

    connection.close()


def _query(url: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}


async def _integration(ctx) -> dict:
    response = await ctx.http.get("/api/v1/integrations")
    integrations = (await response.get_json())["integrations"]
    return next(i for i in integrations if i["id"] == CHATGPT.value)


async def _start(ctx, completion_url=WEB_COMPLETION) -> dict[str, str]:
    response = await ctx.http.post(
        f"/api/v1/integrations/{CHATGPT.value}",
        json={"payload": {}, "completion_url": completion_url},
    )
    assert response.status_code == 200
    return _query((await response.get_json())["link"])


async def _complete(ctx, body: dict):
    return await ctx.http.post(
        f"/api/v1/integrations/{CHATGPT.value}/oauth/complete", json=body
    )


async def _connect(ctx) -> dict[str, str]:
    authorization = await _start(ctx)
    ctx.openai.token_responses.append(
        (200, _tokens(authorization["nonce"], "access-1", "refresh-1"))
    )
    response = await _complete(
        ctx,
        {"state": authorization["state"], "code": "code-1", "client_id": ISSUED},
    )
    assert response.status_code == 204
    return authorization


async def _model_ids(ctx):
    return await ctx.http.get(
        f"/api/v1/labeling/external/providers/{CHATGPT.value}/models"
    )


@pytest.mark.asyncio
async def test_migration_seeds_the_chatgpt_integration(ctx):
    integration = await _integration(ctx)

    assert (integration["name"], integration["type"], integration["status"]) == (
        "ChatGPT",
        "AI_PROVIDER",
        "OFF",
    )
    assert integration["payload_schema"] == {}
    assert integration["available"] is True


@pytest.mark.asyncio
async def test_desktop_sign_in_through_the_backend_callback(ctx):
    authorization = await _start(ctx)

    assert authorization["client_id"] == "dynamic_agent_client"
    assert authorization["redirect_uri"] == f"http://127.0.0.1:{PORT}/auth/callback"
    assert "ext_agent_host_id" not in authorization
    assert (await _integration(ctx))["status"] == "OFF"

    callback = await ctx.http.get(
        "/auth/callback",
        query_string={
            "state": authorization["state"],
            "code": "code-1",
            "client_id": ISSUED,
            "scope": PLAN_SCOPES,
        },
    )

    assert callback.status_code == 302
    location = callback.headers["Location"]
    assert location.startswith("http://localhost:8080/?integration_oauth=CHATGPT&")
    assert location.endswith("#/entities?tab=providers&focus=CHATGPT")
    forwarded = _query(location.split("#")[0])
    assert forwarded == {
        "integration_oauth": "CHATGPT",
        "state": authorization["state"],
        "code": "code-1",
        "client_id": ISSUED,
    }

    ctx.openai.token_responses.append(
        (200, _tokens(authorization["nonce"], "access-1", "refresh-1"))
    )
    response = await _complete(
        ctx,
        {
            "state": forwarded["state"],
            "code": forwarded["code"],
            "client_id": forwarded["client_id"],
        },
    )

    assert response.status_code == 204
    assert (await _integration(ctx))["status"] == "ON"
    stored = await ctx.repository.get_payload(CHATGPT)
    assert stored["client_id"] == ISSUED
    assert stored["access_token"] == "access-1"
    assert stored["refresh_token"] == "refresh-1"
    assert stored["email"] == "user@example.com"
    assert ctx.openai.token_forms[0]["redirect_uri"] == (
        f"http://127.0.0.1:{PORT}/auth/callback"
    )

    models = await _model_ids(ctx)
    assert models.status_code == 200
    assert [model["id"] for model in (await models.get_json())["models"]] == [
        "gpt-6-sol"
    ]


@pytest.mark.asyncio
async def test_unknown_callback_state_is_not_forwarded(ctx):
    await _start(ctx)

    response = await ctx.http.get(
        "/auth/callback", query_string={"state": "forged", "code": "code"}
    )

    assert response.status_code == 400
    assert "Location" not in response.headers
    assert "forged" not in (await response.get_data(as_text=True))


@pytest.mark.asyncio
async def test_mobile_sign_in_uses_the_app_listener(ctx):
    authorization = await _start(ctx, MOBILE_CALLBACK)

    assert authorization["redirect_uri"] == MOBILE_CALLBACK
    forwarded = await ctx.http.get(
        "/auth/callback", query_string={"state": authorization["state"]}
    )
    assert forwarded.status_code == 400

    ctx.openai.token_responses.append(
        (200, _tokens(authorization["nonce"], "access-1", "refresh-1"))
    )
    response = await _complete(
        ctx,
        {"state": authorization["state"], "code": "code-1", "client_id": ISSUED},
    )

    assert response.status_code == 204
    assert ctx.openai.token_forms[0]["redirect_uri"] == MOBILE_CALLBACK
    assert (await _integration(ctx))["status"] == "ON"


@pytest.mark.asyncio
async def test_declined_plan_permission_keeps_the_integration_off(ctx):
    authorization = await _start(ctx)
    tokens = _tokens(authorization["nonce"], "access-1", "refresh-1")
    tokens["scope"] = "openid profile email"
    ctx.openai.token_responses.append((200, tokens))

    response = await _complete(
        ctx,
        {"state": authorization["state"], "code": "code-1", "client_id": ISSUED},
    )

    assert response.status_code == 400
    assert (await response.get_json())["code"] == "AUTHORIZATION_DENIED"
    assert (await _integration(ctx))["status"] == "OFF"


@pytest.mark.asyncio
async def test_rotated_tokens_are_persisted(ctx):
    await _connect(ctx)
    refreshed_at = NOW + timedelta(minutes=58)
    ctx.wall.now = refreshed_at
    ctx.openai.token_responses.append((200, _tokens(None, "access-2", "refresh-2")))

    assert (await _model_ids(ctx)).status_code == 200

    assert ctx.openai.token_forms[-1] == {
        "grant_type": "refresh_token",
        "client_id": ISSUED,
        "refresh_token": "refresh-1",
        "resource": "https://api.openai.com/v1",
    }
    stored = await ctx.repository.get_payload(CHATGPT)
    assert stored["access_token"] == "access-2"
    assert stored["refresh_token"] == "refresh-2"
    assert stored["expires_at"] == (refreshed_at + timedelta(hours=1)).isoformat()
    assert ctx.openai.api_tokens[-1] == "Bearer access-2"


@pytest.mark.asyncio
async def test_reused_refresh_token_expires_and_sign_in_restores_it(ctx):
    await _connect(ctx)
    ctx.wall.now = NOW + timedelta(hours=2)
    ctx.openai.token_responses.append((400, {"error": "refresh_token_reused"}))

    failed = await _model_ids(ctx)

    assert failed.status_code == 502
    assert (await _integration(ctx))["status"] == "EXPIRED"
    assert await ctx.repository.get_payload(CHATGPT) is None
    expired = await ctx.repository.get_payload(CHATGPT, include_expired=True)
    assert expired["refresh_token"] == "refresh-1"

    authorization = await _start(ctx, MOBILE_CALLBACK)

    assert authorization["client_id"] == ISSUED
    assert authorization["login_hint"] == "user@example.com"
    assert "id_token_hint" not in authorization
    assert "agent_name_hint" not in authorization

    ctx.openai.token_responses.append(
        (200, _tokens(authorization["nonce"], "access-3", "refresh-3"))
    )
    response = await _complete(ctx, {"state": authorization["state"], "code": "code-3"})

    assert response.status_code == 204
    assert (await _integration(ctx))["status"] == "ON"
    assert (await ctx.repository.get_payload(CHATGPT))["access_token"] == "access-3"


@pytest.mark.asyncio
async def test_disconnect_revokes_the_session(ctx):
    await _connect(ctx)

    response = await ctx.http.delete(f"/api/v1/integrations/{CHATGPT.value}")

    assert response.status_code == 204
    assert ctx.openai.revocations == [
        {
            "token": "refresh-1",
            "token_type_hint": "refresh_token",
            "client_id": ISSUED,
        }
    ]
    assert (await _integration(ctx))["status"] == "OFF"
    assert await ctx.repository.get_payload(CHATGPT, include_expired=True) is None


@pytest.mark.asyncio
async def test_failed_exchange_retries_with_the_issued_client(ctx):
    first = await _start(ctx)
    ctx.openai.token_responses.append((400, {"error": "invalid_grant"}))

    failed = await _complete(
        ctx, {"state": first["state"], "code": "code-1", "client_id": ISSUED}
    )

    assert failed.status_code == 400
    assert (await failed.get_json())["code"] == "AUTHORIZATION_RETRY_REQUIRED"

    retry = await _start(ctx)
    ctx.openai.token_responses.append(
        (200, _tokens(retry["nonce"], "access-1", "refresh-1"))
    )
    response = await _complete(ctx, {"state": retry["state"], "code": "code-2"})

    assert retry["client_id"] == ISSUED
    assert "agent_name_hint" not in retry
    assert response.status_code == 204
    assert (await _integration(ctx))["status"] == "ON"


@pytest.mark.asyncio
async def test_sign_in_after_disconnect_registers_again(ctx):
    await _connect(ctx)
    await ctx.http.delete(f"/api/v1/integrations/{CHATGPT.value}")

    second = await _start(ctx)

    assert second["client_id"] == "dynamic_agent_client"
    assert second["agent_name_hint"] == "Finanze"
