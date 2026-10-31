from dataclasses import asdict
from unittest.mock import AsyncMock, patch

import pytest

from domain.mcp import McpCategoryAccess, McpToolCategory

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

        assert config == {
            "enabled": False,
            "read_only": True,
            "token": None,
            "category_access": {},
            **mcp_env.catalog.metadata(),
        }
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
            "add_transactions",
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
        for name in ("update_manual_transaction", "delete_manual_transaction"):
            description = tools[name].description
            assert "MANUAL" in description
            assert "REAL" in description
            assert "SHEETS" in description


class TestMcpCategories:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("category", list(McpToolCategory))
    async def test_disabled_category_is_hidden_without_restart(self, mcp_env, category):
        config = await mcp_env.configure(True, False)
        token = config["token"]
        before = await _tool_names(mcp_env, token)

        await mcp_env.configure(
            True,
            False,
            {category.value: {"read_enabled": False, "write_enabled": False}},
        )
        after = await _tool_names(mcp_env, token)

        expected = {
            name for name in before if mcp_env.catalog.get(name).category != category
        }
        assert set(after) == expected
        assert {"get_context", "list_entities"} <= set(after)
        assert len(after) < len(before)

    @pytest.mark.asyncio
    async def test_all_optional_categories_can_be_disabled_and_restored(self, mcp_env):
        config = await mcp_env.configure(True, False)
        token = config["token"]
        before = await _tool_names(mcp_env, token)
        await mcp_env.configure(
            True,
            False,
            {
                category.value: asdict(McpCategoryAccess(False, False))
                for category in McpToolCategory
            },
        )
        assert set(await _tool_names(mcp_env, token)) == {
            "get_context",
            "list_entities",
        }

        await mcp_env.configure(
            True,
            False,
            {
                category.value: asdict(McpCategoryAccess())
                for category in McpToolCategory
            },
        )
        assert set(await _tool_names(mcp_env, token)) == set(before)

    @pytest.mark.asyncio
    async def test_saved_read_only_category_and_global_read_only(self, mcp_env):
        config = await mcp_env.configure(
            True,
            False,
            {"activity_labels": {"read_enabled": True, "write_enabled": False}},
        )
        token = config["token"]
        tools = await _tool_names(mcp_env, token)
        assert "list_labels" in tools and "save_label" not in tools
        assert "save_periodic_flow" in tools

        await mcp_env.configure(True, True)
        assert all(
            tool.annotations.read_only_hint
            for tool in (await _tool_names(mcp_env, token)).values()
        )
        await mcp_env.configure(True, False)
        tools = await _tool_names(mcp_env, token)
        assert "save_label" not in tools and "save_periodic_flow" in tools

    @pytest.mark.asyncio
    async def test_stale_read_and_direct_write_calls_cannot_execute(self, mcp_env):
        config = await mcp_env.configure(True, False)
        async with mcp_env.connect(config["token"]) as client:
            await client.list_tools()
            await mcp_env.configure(
                True,
                False,
                {"activity_labels": {"read_enabled": False, "write_enabled": False}},
            )
            with patch.object(
                mcp_env.ucs.get_labels, "execute", new_callable=AsyncMock
            ) as execute:
                result = await client.call_tool("list_labels", {})
                assert result.is_error
                assert "disabled" in result.content[0].text
                execute.assert_not_awaited()
            with patch.object(
                mcp_env.ucs.create_label, "execute", new_callable=AsyncMock
            ) as execute:
                result = await client.call_tool(
                    "save_label", {"name": "Blocked", "category": "EXPENSE"}
                )
                assert result.is_error
                execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_preferences_survive_flags_rotation_and_repository_reload(
        self, mcp_env
    ):
        preferences = {"positions": {"read_enabled": False, "write_enabled": False}}
        config = await mcp_env.configure(True, False, preferences)
        await mcp_env.configure(False, True)
        await mcp_env.configure(True, False)
        async with mcp_env.http() as http_client:
            rotated = (await http_client.post("/api/v1/mcp/config/token")).json()
            loaded = (await http_client.get("/api/v1/mcp/config")).json()
        assert rotated["category_access"] == loaded["category_access"] == preferences
        assert rotated["token"] != config["token"]
        assert (
            asdict(await mcp_env.config_repository.get())["category_access"]
            == preferences
        )
        assert "get_positions" not in await _tool_names(mcp_env, rotated["token"])

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "preferences",
        [
            {"positions": {"read_enabled": False, "write_enabled": True}},
            {"positions": {"read_enabled": "false", "write_enabled": False}},
            {"essential": {}},
            {"unknown": {}},
            [],
        ],
    )
    async def test_invalid_preferences_return_400(self, mcp_env, preferences):
        async with mcp_env.http() as http_client:
            response = await http_client.put(
                "/api/v1/mcp/config",
                json={
                    "enabled": True,
                    "read_only": True,
                    "category_access": preferences,
                },
            )
        assert response.status_code == 400
        assert (await mcp_env.config_repository.get()).enabled is False

    @pytest.mark.asyncio
    async def test_metadata_matches_full_catalog_and_merged_groups(self, mcp_env):
        config = await mcp_env.configure(True, False)
        tools = await _tool_names(mcp_env, config["token"])
        async with mcp_env.http() as http_client:
            response = await http_client.get("/api/v1/mcp/config")
        metadata = response.json()
        assert metadata["essential_count"] == 2
        assert metadata["essential_tools"] == ["get_context", "list_entities"]
        assert len(metadata["tool_categories"]) == 9
        assert sum(
            row["read_count"] + row["write_count"]
            for row in metadata["tool_categories"]
        ) + 2 == len(tools)
        names = list(metadata["essential_tools"])
        for category in metadata["tool_categories"]:
            for access, read_only in (("read", True), ("write", False)):
                tool_names = category[f"{access}_tools"]
                assert tool_names == sorted(tool_names)
                assert len(tool_names) == category[f"{access}_count"]
                for name in tool_names:
                    assert mcp_env.catalog.get(name).category.value == category["id"]
                    assert tools[name].annotations.read_only_hint is read_only
                names.extend(tool_names)
        assert len(names) == len(set(names))
        assert set(names) == set(tools)
        for name in (
            "get_historic_positions",
            "list_pending_flows",
            "save_pending_flow",
            "settle_pending_flow",
            "settle_manual_investment",
            "save_commodities",
        ):
            assert mcp_env.catalog.get(name).category == McpToolCategory.POSITIONS
        for name in (
            "get_contributions",
            "save_contribution",
            "delete_contribution",
            "list_periodic_flows",
        ):
            assert mcp_env.catalog.get(name).category == McpToolCategory.BUDGET
