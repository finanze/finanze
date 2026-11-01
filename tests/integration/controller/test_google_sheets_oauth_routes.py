import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

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
from application.use_cases.get_external_integrations import (
    GetExternalIntegrationsImpl,
)
from domain.data_init import DatasourceInitContext
from domain.external_integration import ExternalIntegrationId
from google_auth_oauthlib.flow import Flow
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
from infrastructure.controller.routes.get_external_integrations import (
    get_external_integrations,
)
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import versions
from infrastructure.repository.external_integration.external_integration_repository import (
    ExternalIntegrationRepository,
)
from infrastructure.sheets.sheets_service_loader import (
    SCOPES,
    TOKEN_FILENAME,
    SheetsServiceLoader,
)

SHEETS = ExternalIntegrationId.GOOGLE_SHEETS
PAYLOAD = {"client_id": "client-id", "client_secret": "client-secret"}
COMPLETION_URL = (
    "http://localhost:8080/?integration_oauth=GOOGLE_SHEETS"
    "#/entities?tab=providers&focus=GOOGLE_SHEETS"
)
TOKEN = {"access_token": "access", "refresh_token": "refresh", "scope": SCOPES}


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

    loader = SheetsServiceLoader()
    loader.connect(SimpleNamespace(path=tmp_path))
    integrations = {SHEETS: loader}

    get_uc = GetExternalIntegrationsImpl(repository, integrations)
    connect_uc = ConnectExternalIntegrationImpl(repository, integrations)
    complete_uc = CompleteExternalIntegrationConnectionImpl(repository, integrations)
    disconnect_uc = DisconnectExternalIntegrationImpl(repository, integrations)

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

    yield SimpleNamespace(http=app.test_client(), repository=repository, path=tmp_path)

    connection.close()


async def _status(ctx) -> str:
    response = await ctx.http.get("/api/v1/integrations")
    integrations = (await response.get_json())["integrations"]
    return next(i["status"] for i in integrations if i["id"] == SHEETS.value)


async def _connect(ctx, completion_url=COMPLETION_URL):
    return await ctx.http.post(
        f"/api/v1/integrations/{SHEETS.value}",
        json={"payload": PAYLOAD, "completion_url": completion_url},
    )


async def _start(ctx) -> str:
    response = await _connect(ctx)
    assert response.status_code == 200
    link = (await response.get_json())["link"]
    return parse_qs(urlsplit(link).query)["state"][0]


async def _complete(ctx, body: dict):
    return await ctx.http.post(
        f"/api/v1/integrations/{SHEETS.value}/oauth/complete", json=body
    )


@pytest.mark.asyncio
async def test_connect_returns_authorization_link_without_activating(ctx):
    response = await _connect(ctx)

    assert response.status_code == 200
    link = (await response.get_json())["link"]
    assert link.startswith("https://accounts.google.com/o/oauth2/auth?")
    assert await _status(ctx) == "OFF"
    assert await ctx.repository.get_payload(SHEETS) is None


@pytest.mark.asyncio
async def test_complete_activates_integration_with_refresh_token(ctx):
    state = await _start(ctx)

    with patch.object(Flow, "fetch_token", return_value=TOKEN):
        response = await _complete(ctx, {"state": state, "code": "auth-code"})

    assert response.status_code == 204
    assert await _status(ctx) == "ON"
    assert await ctx.repository.get_payload(SHEETS) == {
        **PAYLOAD,
        "refresh_token": "refresh",
    }


@pytest.mark.asyncio
async def test_denied_authorization_keeps_integration_off(ctx):
    state = await _start(ctx)

    response = await _complete(ctx, {"state": state, "error": "access_denied"})

    assert response.status_code == 400
    assert (await response.get_json())["code"] == "AUTHORIZATION_DENIED"
    assert await _status(ctx) == "OFF"


@pytest.mark.asyncio
async def test_unknown_state_is_rejected(ctx):
    await _start(ctx)

    response = await _complete(ctx, {"state": "forged", "code": "auth-code"})

    assert response.status_code == 400
    assert (await response.get_json())["code"] == "AUTHORIZATION_EXPIRED"
    assert await _status(ctx) == "OFF"


@pytest.mark.asyncio
async def test_missing_state_is_rejected(ctx):
    response = await _complete(ctx, {"code": "auth-code"})
    assert response.status_code == 400


@pytest.mark.parametrize(
    "completion_url",
    ["javascript:alert(1)", "/relative", "ftp://host/path", 42],
)
@pytest.mark.asyncio
async def test_invalid_completion_url_is_rejected(ctx, completion_url):
    response = await _connect(ctx, completion_url)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_desktop_completion_deeplink_is_accepted(ctx):
    response = await _connect(
        ctx, "finanze://integration/complete?integration_oauth=GOOGLE_SHEETS"
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_disconnect_removes_legacy_token(ctx):
    (ctx.path / TOKEN_FILENAME).write_text(json.dumps({"token": "legacy"}))
    state = await _start(ctx)
    with patch.object(Flow, "fetch_token", return_value=TOKEN):
        await _complete(ctx, {"state": state, "code": "auth-code"})

    response = await ctx.http.delete(f"/api/v1/integrations/{SHEETS.value}")

    assert response.status_code == 204
    assert await _status(ctx) == "OFF"
    assert not (ctx.path / TOKEN_FILENAME).exists()
