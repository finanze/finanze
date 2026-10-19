import pytest

INIT_PAYLOAD = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"},
    },
}
ACCEPT = {"Accept": "application/json, text/event-stream"}


async def _post_mcp(env, token=None):
    async with env.http(token) as http_client:
        return await http_client.post("/mcp", json=INIT_PAYLOAD, headers=ACCEPT)


async def _tool_names(env, token):
    async with env.connect(token) as client:
        return {tool.name: tool for tool in (await client.list_tools()).tools}


class TestMcpAccess:
    @pytest.mark.asyncio
    async def test_disabled_by_default(self, mcp_env):
        async with mcp_env.http() as http_client:
            config = (await http_client.get("/api/v1/mcp/config")).json()

        assert config == {"enabled": False, "read_only": True, "token": None}
        assert (await _post_mcp(mcp_env)).status_code == 404

    @pytest.mark.asyncio
    async def test_rest_api_is_still_served(self, mcp_env):
        async with mcp_env.http() as http_client:
            response = await http_client.get("/api/v1/ping")

        assert response.status_code == 200
        assert response.json() == {"pong": True}

    @pytest.mark.asyncio
    async def test_enabling_generates_token_and_requires_it(self, mcp_env):
        config = await mcp_env.configure(enabled=True, read_only=True)
        assert config["token"]

        missing = await _post_mcp(mcp_env)
        assert missing.status_code == 401
        assert missing.headers["www-authenticate"] == "Bearer"
        assert (await _post_mcp(mcp_env, "wrong-token")).status_code == 401

        tools = await _tool_names(mcp_env, config["token"])
        assert "get_net_worth" in tools
        assert "save_label" not in tools
        assert all(tool.annotations.read_only_hint for tool in tools.values())

    @pytest.mark.asyncio
    async def test_disabling_read_only_exposes_write_tools(self, mcp_env):
        config = await mcp_env.configure(enabled=True, read_only=False)

        tools = await _tool_names(mcp_env, config["token"])

        assert tools["save_label"].annotations.read_only_hint is False
        assert tools["delete_label"].annotations.destructive_hint is True
        assert tools["get_net_worth"].annotations.read_only_hint is True
        for name in (
            "save_manual_position",
            "save_contribution",
            "settle_manual_investment",
            "amortize_manual_investment",
            "unsettle_manual_investment",
        ):
            assert tools[name].annotations.read_only_hint is False, name
            assert tools[name].annotations.destructive_hint is False, name
        for name in (
            "delete_manual_position",
            "delete_contribution",
            "delete_manual_historic_entry",
        ):
            assert tools[name].annotations.destructive_hint is True, name

    @pytest.mark.asyncio
    async def test_regenerated_token_replaces_previous(self, mcp_env):
        old_token = (await mcp_env.configure(enabled=True, read_only=True))["token"]

        async with mcp_env.http() as http_client:
            response = await http_client.post("/api/v1/mcp/config/token")
        new_token = response.json()["token"]

        assert new_token and new_token != old_token
        assert (await _post_mcp(mcp_env, old_token)).status_code == 401
        assert "get_context" in await _tool_names(mcp_env, new_token)

    @pytest.mark.asyncio
    async def test_disabling_rejects_and_keeps_token(self, mcp_env):
        token = (await mcp_env.configure(enabled=True, read_only=False))["token"]

        disabled = await mcp_env.configure(enabled=False, read_only=False)
        assert (await _post_mcp(mcp_env, token)).status_code == 404

        enabled = await mcp_env.configure(enabled=True, read_only=True)
        assert disabled["token"] == token
        assert enabled["token"] == token

    @pytest.mark.asyncio
    async def test_locked_finanze_returns_unavailable(self, mcp_env):
        token = (await mcp_env.configure(enabled=True, read_only=True))["token"]

        await mcp_env.db_manager.lock()

        assert (await _post_mcp(mcp_env, token)).status_code == 503

    @pytest.mark.asyncio
    async def test_tool_catalog_is_described(self, mcp_env):
        token = (await mcp_env.configure(enabled=True, read_only=False))["token"]

        tools = await _tool_names(mcp_env, token)

        assert len(tools) > 40
        for tool in tools.values():
            assert tool.description, tool.name
            assert tool.annotations.title, tool.name
