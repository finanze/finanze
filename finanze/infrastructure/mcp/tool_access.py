from typing import Any

from domain.mcp import McpAuthorization
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.types import CallToolResult, TextContent

from infrastructure.mcp.gateway import MCP_AUTHORIZATION_STATE
from infrastructure.mcp.tool_catalog import McpToolCatalog


class McpToolAccess:
    def __init__(self, catalog: McpToolCatalog):
        self._catalog = catalog

    async def __call__(
        self, ctx: ServerRequestContext[Any, Any], call_next: CallNext
    ) -> HandlerResult:
        if ctx.method not in ("tools/list", "tools/call"):
            return await call_next(ctx)

        state = ctx.request.scope.get("state", {}) if ctx.request is not None else {}
        authorization = state.get(MCP_AUTHORIZATION_STATE)
        if not isinstance(authorization, McpAuthorization):
            authorization = None

        if ctx.method == "tools/call":
            name = (ctx.params or {}).get("name")
            if (
                isinstance(name, str)
                and self._catalog.get(name) is not None
                and not self._catalog.allows(name, authorization)
            ):
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text="This tool is disabled in Finanze MCP settings. Ask the user to enable its category and required access before trying again.",
                        )
                    ],
                    is_error=True,
                ).model_dump(mode="json", by_alias=True, exclude_none=True)
            return await call_next(ctx)

        result = await call_next(ctx)
        if isinstance(result, dict) and isinstance(result.get("tools"), list):
            return {
                **result,
                "tools": [
                    tool
                    for tool in result["tools"]
                    if self._catalog.allows(tool["name"], authorization)
                ],
            }
        return result
