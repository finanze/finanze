import json
from unittest.mock import AsyncMock

import pytest
from domain.mcp import McpAccess, McpAuthorization
from domain.use_cases.authorize_mcp_access import AuthorizeMcpAccess

from infrastructure.mcp.gateway import MCP_AUTHORIZATION_STATE, McpGateway


class RecordingApp:
    def __init__(self):
        self.scopes = []

    async def __call__(self, scope, receive, send):
        self.scopes.append(scope)


def _scope(path="/mcp", headers=None, scope_type="http"):
    return {"type": scope_type, "path": path, "headers": headers or []}


async def _run(gateway, scope):
    messages = []

    async def send(message):
        messages.append(message)

    await gateway(scope, AsyncMock(), send)
    return messages


@pytest.fixture
def setup():
    authorize = AsyncMock(spec=AuthorizeMcpAccess)
    apps = RecordingApp(), RecordingApp(), RecordingApp()
    gateway = McpGateway(*apps, authorize)
    return gateway, authorize, apps


class TestMcpGateway:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "scope",
        [
            _scope(path="/api/v1/status"),
            _scope(path="/mcpx"),
            _scope(scope_type="lifespan"),
        ],
    )
    async def test_non_mcp_traffic_goes_to_default_app(self, setup, scope):
        gateway, authorize, (default_app, read_app, full_app) = setup

        await _run(gateway, scope)

        assert default_app.scopes == [scope]
        authorize.execute.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "access,app_index",
        [(McpAccess.READ_ONLY, 1), (McpAccess.READ_WRITE, 2)],
    )
    async def test_routes_by_access(self, setup, access, app_index):
        gateway, authorize, apps = setup
        authorization = McpAuthorization(access)
        authorize.execute.return_value = authorization
        scope = _scope(path="/mcp/", headers=[(b"authorization", b"Bearer abc ")])

        await _run(gateway, scope)

        authorize.execute.assert_awaited_once_with("abc")
        forwarded = apps[app_index].scopes[0]
        assert forwarded["state"][MCP_AUTHORIZATION_STATE] == authorization
        assert "state" not in scope
        assert forwarded["path"] == scope["path"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "header",
        [None, b"Basic abc", b"Bearer ", b"bearer"],
    )
    async def test_missing_or_invalid_bearer_passes_no_token(self, setup, header):
        gateway, authorize, _ = setup
        authorize.execute.return_value = McpAuthorization(McpAccess.UNAUTHORIZED)
        headers = [(b"authorization", header)] if header else []

        await _run(gateway, _scope(headers=headers))

        authorize.execute.assert_awaited_once_with(None)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "access,status",
        [
            (McpAccess.DISABLED, 404),
            (McpAccess.LOCKED, 503),
            (McpAccess.UNAUTHORIZED, 401),
        ],
    )
    async def test_denied_responses(self, setup, access, status):
        gateway, authorize, apps = setup
        authorize.execute.return_value = McpAuthorization(access)

        start, body = await _run(gateway, _scope())

        assert start["status"] == status
        assert json.loads(body["body"])["message"]
        assert all(not app.scopes for app in apps)
        assert ((b"www-authenticate", b"Bearer") in start["headers"]) == (status == 401)
