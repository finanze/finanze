import sqlite3
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from application.use_cases.connect_external_integration import (
    ConnectExternalIntegrationImpl,
)
from application.use_cases.disconnect_external_integration import (
    DisconnectExternalIntegrationImpl,
)
from application.use_cases.get_external_integrations import (
    GetExternalIntegrationsImpl,
)
from application.use_cases.get_external_labeling_models import (
    GetExternalLabelingModelsImpl,
)
from application.use_cases.poll_external_integration_connection import (
    PollExternalIntegrationConnectionImpl,
)
from dateutil.tz import tzlocal
from domain.data_init import DatasourceInitContext
from domain.external_integration import ExternalIntegrationId
from infrastructure.agent_runtime.runtime_pool import AgentRuntimePool
from infrastructure.agent_runtime.runtime_sandbox import AgentRuntimeSandbox
from infrastructure.client.ai.github_copilot.copilot_runtime_provisioner import (
    CLI_PATH_ENV,
    CopilotRuntimeProvisioner,
)
from infrastructure.client.ai.github_copilot.copilot_runtime_types import (
    CopilotModelEntry,
)
from infrastructure.client.ai.github_copilot.github_copilot_client import (
    GITHUB_DEVICE_SCOPE,
    PROVIDER,
    GitHubCopilotClient,
)
from infrastructure.client.ai.github_copilot.github_device_flow import (
    ACCESS_TOKEN_URL,
    DEVICE_CODE_URL,
    REFRESH_GRANT_TYPE,
    VERIFICATION_URI,
    GitHubDeviceFlow,
)
from infrastructure.client.http.http_response import HttpResponse
from infrastructure.controller.config import quart
from infrastructure.controller.exception_handler import register_exception_handlers
from infrastructure.controller.routes.connect_external_integration import (
    connect_external_integration,
)
from infrastructure.controller.routes.disconnect_external_integration import (
    disconnect_external_integration,
)
from infrastructure.controller.routes.get_external_integrations import (
    get_external_integrations,
)
from infrastructure.controller.routes.get_external_labeling_models import (
    get_external_labeling_models,
)
from infrastructure.controller.routes.poll_external_integration_connection import (
    poll_external_integration_connection,
)
from infrastructure.labeling.ai_labeling_presets import LABELING_PRESETS
from infrastructure.labeling.ai_labeling_provider import AILabelingProvider
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import versions
from infrastructure.repository.external_integration.external_integration_repository import (
    ExternalIntegrationRepository,
)

COPILOT = ExternalIntegrationId.GITHUB_COPILOT
DEVICE_CODE = "device-code-secret"
TOKEN = "gho_device_token"
MODELS = [CopilotModelEntry(id="gpt-5-mini", name="GPT-5 mini", enabled=True)]
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=tzlocal())
ACCESS_TTL = timedelta(hours=8)
REFRESH_TTL = timedelta(days=184)


def _expiring_response(access_token: str, refresh_token: str) -> dict:
    return {
        "access_token": access_token,
        "expires_in": int(ACCESS_TTL.total_seconds()),
        "refresh_token": refresh_token,
        "refresh_token_expires_in": int(REFRESH_TTL.total_seconds()),
        "scope": "",
        "token_type": "bearer",
    }


def _expiring_payload(access_token: str, refresh_token: str, issued_at) -> dict:
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_at": (issued_at + ACCESS_TTL).isoformat(),
        "refresh_token_expires_at": (issued_at + REFRESH_TTL).isoformat(),
    }


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class WallClock:
    def __init__(self):
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


class FakeRuntime:
    def __init__(self, models):
        self.models = models
        self.stopped = False

    async def stop(self):
        self.stopped = True

    async def is_authenticated(self):
        return True

    async def list_models(self):
        return list(self.models)

    async def complete(self, **kwargs):
        return None


class FakeGitHub:
    def __init__(self):
        self.token_responses: list[dict] = []
        self.token_requests: list[dict] = []

    async def post(self, url, **kwargs):
        if url == DEVICE_CODE_URL:
            body = {
                "device_code": DEVICE_CODE,
                "user_code": "ABCD-1234",
                "verification_uri": VERIFICATION_URI,
                "expires_in": 900,
                "interval": 5,
            }
        else:
            assert url == ACCESS_TOKEN_URL
            self.token_requests.append(kwargs["data"])
            body = self.token_responses.pop(0)
        return HttpResponse(httpx.Response(200, json=body))


@pytest_asyncio.fixture
async def ctx(tmp_path, monkeypatch):
    monkeypatch.setenv(CLI_PATH_ENV, "/runtime/copilot")
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    client = DBClient(connection)
    await DatabaseUpgrader(
        client, versions, DatasourceInitContext(config=AsyncMock())
    ).upgrade()
    repository = ExternalIntegrationRepository(client)

    clock = Clock()
    wall = WallClock()
    github = FakeGitHub()
    runtimes: list[FakeRuntime] = []
    state = SimpleNamespace(models=MODELS, started=[])

    async def runtime_factory(executable, token, dirs):
        state.started.append((executable, token))
        runtime = FakeRuntime(state.models)
        runtimes.append(runtime)
        return runtime

    sandbox = AgentRuntimeSandbox(tmp_path / "agent_runtimes")
    pool = AgentRuntimePool()
    copilot = GitHubCopilotClient(
        GitHubDeviceFlow("Iv1.client", GITHUB_DEVICE_SCOPE, github, clock, wall),
        CopilotRuntimeProvisioner(sandbox.runtime_dir(PROVIDER)),
        pool,
        sandbox,
        repository,
        runtime_factory=runtime_factory,
        now=wall,
    )
    integrations = {COPILOT: copilot}

    get_uc = GetExternalIntegrationsImpl(repository, integrations)
    connect_uc = ConnectExternalIntegrationImpl(repository, integrations)
    poll_uc = PollExternalIntegrationConnectionImpl(repository, integrations)
    disconnect_uc = DisconnectExternalIntegrationImpl(repository, integrations)
    models_uc = GetExternalLabelingModelsImpl(
        repository, {COPILOT: AILabelingProvider(copilot, LABELING_PRESETS[COPILOT])}
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

    @app.route("/api/v1/integrations/<integration_id>/device/poll", methods=["POST"])
    async def poll_route(integration_id: str):
        return await poll_external_integration_connection(poll_uc, integration_id)

    @app.route(
        "/api/v1/labeling/external/providers/<provider_id>/models", methods=["GET"]
    )
    async def models_route(provider_id: str):
        return await get_external_labeling_models(models_uc, provider_id)

    yield SimpleNamespace(
        http=app.test_client(),
        repository=repository,
        copilot=copilot,
        clock=clock,
        wall=wall,
        github=github,
        runtimes=runtimes,
        state=state,
    )

    await pool.release_all()
    connection.close()


async def _integration(ctx) -> dict:
    response = await ctx.http.get("/api/v1/integrations")
    integrations = (await response.get_json())["integrations"]
    return next(i for i in integrations if i["id"] == COPILOT.value)


async def _start(ctx) -> dict:
    response = await ctx.http.post(
        f"/api/v1/integrations/{COPILOT.value}", json={"payload": {}}
    )
    assert response.status_code == 200
    return (await response.get_json())["device"]


async def _poll(ctx, flow_id):
    return await ctx.http.post(
        f"/api/v1/integrations/{COPILOT.value}/device/poll",
        json={"flow_id": flow_id},
    )


@pytest.mark.asyncio
async def test_device_flow_connects_github_copilot(ctx):
    integration = await _integration(ctx)
    assert integration["available"] is True
    assert integration["status"] == "OFF"
    assert integration["payload_schema"] == {}

    device = await _start(ctx)

    assert device["user_code"] == "ABCD-1234"
    assert device["verification_uri"] == VERIFICATION_URI
    assert device["interval"] == 5
    assert 890 <= device["expires_in"] <= 900
    assert DEVICE_CODE not in str(device)

    early = await _poll(ctx, device["flow_id"])
    assert await early.get_json() == {"status": "PENDING", "interval": 5}

    ctx.github.token_responses = [
        {"error": "authorization_pending"},
        {"access_token": TOKEN, "token_type": "bearer", "scope": "read:user"},
    ]
    ctx.clock.now = 5
    pending = await _poll(ctx, device["flow_id"])
    assert await pending.get_json() == {"status": "PENDING", "interval": 5}

    ctx.clock.now = 10
    connected = await _poll(ctx, device["flow_id"])

    assert connected.status_code == 200
    assert await connected.get_json() == {"status": "CONNECTED"}
    assert ctx.state.started == [("/runtime/copilot", TOKEN)]
    assert (await _integration(ctx))["status"] == "ON"
    assert await ctx.repository.get_payload(COPILOT) == {
        "access_token": TOKEN,
        "token_type": "bearer",
        "scope": "read:user",
    }


@pytest.mark.asyncio
async def test_denied_authorization_keeps_integration_off(ctx):
    device = await _start(ctx)
    ctx.github.token_responses = [{"error": "access_denied"}]
    ctx.clock.now = 5

    response = await _poll(ctx, device["flow_id"])

    assert response.status_code == 400
    assert (await response.get_json())["code"] == "AUTHORIZATION_DENIED"
    assert (await _integration(ctx))["status"] == "OFF"
    assert ctx.state.started == []


@pytest.mark.asyncio
async def test_account_without_copilot_models_is_not_entitled(ctx):
    ctx.state.models = [CopilotModelEntry(id="x", name="X", enabled=False)]
    device = await _start(ctx)
    ctx.github.token_responses = [{"access_token": TOKEN}]
    ctx.clock.now = 5

    response = await _poll(ctx, device["flow_id"])

    assert response.status_code == 400
    assert (await response.get_json())["code"] == "NOT_ENTITLED"
    assert (await _integration(ctx))["status"] == "OFF"
    assert await ctx.repository.get_payload(COPILOT) is None
    assert ctx.runtimes[0].stopped


@pytest.mark.asyncio
async def test_disconnect_stops_runtime(ctx):
    device = await _start(ctx)
    ctx.github.token_responses = [{"access_token": TOKEN}]
    ctx.clock.now = 5
    assert (await _poll(ctx, device["flow_id"])).status_code == 200

    response = await ctx.http.delete(f"/api/v1/integrations/{COPILOT.value}")

    assert response.status_code == 204
    assert ctx.runtimes[0].stopped
    assert (await _integration(ctx))["status"] == "OFF"


@pytest.mark.parametrize(
    "integration_id, body, status, code",
    [
        (COPILOT.value, {}, 400, None),
        (COPILOT.value, {"flow_id": 42}, 400, None),
        ("UNKNOWN", {"flow_id": "flow"}, 400, None),
        (COPILOT.value, {"flow_id": "forged"}, 400, "AUTHORIZATION_EXPIRED"),
        ("OPENAI", {"flow_id": "flow"}, 404, "INTEGRATION_NOT_FOUND"),
    ],
)
@pytest.mark.asyncio
async def test_poll_rejects_invalid_requests(ctx, integration_id, body, status, code):
    response = await ctx.http.post(
        f"/api/v1/integrations/{integration_id}/device/poll", json=body
    )

    assert response.status_code == status
    if code:
        assert (await response.get_json())["code"] == code


@pytest.mark.asyncio
async def test_migration_seeds_github_copilot_integration(ctx):
    integration = await _integration(ctx)
    assert (integration["name"], integration["type"]) == (
        "GitHub Copilot",
        "AI_PROVIDER",
    )


async def _connect(ctx, token_response: dict):
    device = await _start(ctx)
    ctx.github.token_responses = [token_response]
    ctx.clock.now = 5
    assert (await _poll(ctx, device["flow_id"])).status_code == 200


async def _model_ids(ctx) -> list[str]:
    response = await ctx.http.get(
        f"/api/v1/labeling/external/providers/{COPILOT.value}/models"
    )
    assert response.status_code == 200
    return [model["id"] for model in (await response.get_json())["models"]]


@pytest.mark.asyncio
async def test_expiring_token_is_refreshed_and_rotation_persisted(ctx):
    await _connect(ctx, _expiring_response("ghu_first", "ghr_first"))

    assert await ctx.repository.get_payload(COPILOT) == _expiring_payload(
        "ghu_first", "ghr_first", NOW
    )
    assert await _model_ids(ctx) == ["gpt-5-mini"]
    assert len(ctx.github.token_requests) == 1

    refreshed_at = NOW + ACCESS_TTL - timedelta(minutes=2)
    ctx.wall.now = refreshed_at
    ctx.github.token_responses = [_expiring_response("ghu_second", "ghr_second")]

    assert await _model_ids(ctx) == ["gpt-5-mini"]

    assert ctx.github.token_requests[-1] == {
        "client_id": "Iv1.client",
        "grant_type": REFRESH_GRANT_TYPE,
        "refresh_token": "ghr_first",
    }
    assert await ctx.repository.get_payload(COPILOT) == _expiring_payload(
        "ghu_second", "ghr_second", refreshed_at
    )
    assert [token for _, token in ctx.state.started] == ["ghu_first", "ghu_second"]
    assert ctx.runtimes[0].stopped
    assert (await _integration(ctx))["status"] == "ON"

    assert await _model_ids(ctx) == ["gpt-5-mini"]
    assert len(ctx.github.token_requests) == 2


@pytest.mark.asyncio
async def test_refresh_after_disconnect_does_not_reconnect(ctx):
    await _connect(ctx, _expiring_response("ghu_first", "ghr_first"))
    stale = await ctx.repository.get_payload(COPILOT)
    assert (
        await ctx.http.delete(f"/api/v1/integrations/{COPILOT.value}")
    ).status_code == 204

    ctx.wall.now = NOW + ACCESS_TTL - timedelta(minutes=2)
    ctx.github.token_responses = [_expiring_response("ghu_second", "ghr_second")]
    await ctx.copilot.list_models(stale)

    assert (await _integration(ctx))["status"] == "OFF"
    assert await ctx.repository.get_payload(COPILOT) is None
