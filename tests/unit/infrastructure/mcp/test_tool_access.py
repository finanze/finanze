from unittest.mock import AsyncMock, MagicMock

import pytest
from domain.mcp import McpAccess, McpAuthorization, McpCategoryAccess, McpToolCategory
from mcp.server.context import ServerRequestContext
from starlette.requests import Request

from infrastructure.mcp.gateway import MCP_AUTHORIZATION_STATE
from infrastructure.mcp.tool_access import McpToolAccess
from infrastructure.mcp.tool_catalog import McpToolCatalog


def _catalog():
    catalog = McpToolCatalog()
    catalog.add("get_context", "Context", None, True)
    catalog.add("get_positions", "Positions", "positions", True)
    catalog.add("save_position", "Save position", "positions", False)
    return catalog


def _context(method, authorization=None, params=None):
    return ServerRequestContext(
        session=MagicMock(),
        lifespan_context={},
        protocol_version="2025-06-18",
        method=method,
        params=params,
        request=Request(
            {
                "type": "http",
                "state": {MCP_AUTHORIZATION_STATE: authorization}
                if authorization
                else {},
            }
        ),
    )


class TestMcpToolCatalog:
    def test_metadata_returns_sorted_read_and_write_names_with_matching_counts(self):
        catalog = _catalog()
        catalog.add("get_accounts", "Accounts", "positions", True)
        metadata = catalog.metadata()

        assert metadata["essential_tools"] == ["get_context"]
        assert metadata["essential_count"] == 1
        positions = next(
            category
            for category in metadata["tool_categories"]
            if category["id"] == "positions"
        )
        assert positions["read_tools"] == ["get_accounts", "get_positions"]
        assert positions["write_tools"] == ["save_position"]
        for category in metadata["tool_categories"]:
            assert category["read_count"] == len(category["read_tools"])
            assert category["write_count"] == len(category["write_tools"])
        metadata["essential_tools"].clear()
        positions["read_tools"].clear()
        assert catalog.metadata()["essential_tools"] == ["get_context"]
        assert catalog.metadata()["tool_categories"][0]["read_tools"] == [
            "get_accounts",
            "get_positions",
        ]

    @pytest.mark.parametrize("access", [McpAccess.READ_ONLY, McpAccess.READ_WRITE])
    @pytest.mark.parametrize(
        "preferences",
        [
            None,
            McpCategoryAccess(),
            McpCategoryAccess(True, False),
            McpCategoryAccess(False, False),
        ],
    )
    def test_effective_access(self, access, preferences):
        catalog = _catalog()
        policy = {} if preferences is None else {McpToolCategory.POSITIONS: preferences}
        authorization = McpAuthorization(access, policy)
        readable = preferences is None or preferences.read_enabled
        writable = access == McpAccess.READ_WRITE and (
            preferences is None or preferences.write_enabled
        )
        assert catalog.allows("get_context", authorization)
        assert catalog.allows("get_positions", authorization) == readable
        assert catalog.allows("save_position", authorization) == writable
        assert not catalog.allows("unknown", authorization)

    def test_registration_is_deduplicated_and_conflicts_fail(self):
        catalog = _catalog()
        before = catalog.metadata()
        catalog.add("get_positions", "Positions", "positions", True)
        assert catalog.metadata() == before
        with pytest.raises(ValueError, match="Conflicting"):
            catalog.add("get_positions", "Positions", "budget", True)
        with pytest.raises(ValueError):
            catalog.add("invalid", "Invalid", "", True)
        with pytest.raises(ValueError, match="Essential"):
            catalog.add("invalid", "Invalid", None, False)


class TestMcpToolAccess:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "authorization", [None, McpAuthorization(McpAccess.UNAUTHORIZED)]
    )
    async def test_missing_or_denied_authorization_fails_closed(self, authorization):
        middleware = McpToolAccess(_catalog())
        call_next = AsyncMock(return_value={"tools": [{"name": "get_context"}]})
        result = await middleware(_context("tools/list", authorization), call_next)
        assert result["tools"] == []
        call_next.reset_mock()
        result = await middleware(
            _context("tools/call", authorization, {"name": "get_context"}), call_next
        )
        assert result["isError"] is True
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_filter_preserves_metadata_and_does_not_mutate_catalog_result(self):
        result = {
            "tools": [{"name": "get_context"}, {"name": "get_positions"}],
            "nextCursor": "cursor",
            "_meta": {"test": True},
        }
        call_next = AsyncMock(return_value=result)
        middleware = McpToolAccess(_catalog())
        authorization = McpAuthorization(
            McpAccess.READ_WRITE,
            {McpToolCategory.POSITIONS: McpCategoryAccess(False, False)},
        )
        filtered = await middleware(_context("tools/list", authorization), call_next)
        assert filtered == {**result, "tools": [{"name": "get_context"}]}
        assert len(result["tools"]) == 2
        unfiltered = await middleware(
            _context("tools/list", McpAuthorization(McpAccess.READ_WRITE)), call_next
        )
        assert unfiltered == result

    @pytest.mark.asyncio
    async def test_unknown_tools_and_other_methods_keep_sdk_behavior(self):
        call_next = AsyncMock(return_value={"result": True})
        middleware = McpToolAccess(_catalog())
        for method, params in [
            ("initialize", None),
            ("tools/call", {"name": "unknown"}),
            ("tools/call", {"name": []}),
        ]:
            assert await middleware(_context(method, params=params), call_next) == {
                "result": True
            }
        assert call_next.await_count == 3
