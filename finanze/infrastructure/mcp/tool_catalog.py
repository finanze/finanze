from dataclasses import dataclass

from domain.mcp import McpAccess, McpAuthorization, McpToolCategory


@dataclass(frozen=True)
class McpTool:
    name: str
    title: str
    category: McpToolCategory | None
    read_only: bool


class McpToolCatalog:
    def __init__(self):
        self._tools: dict[str, McpTool] = {}

    def add(self, name: str, title: str, category: str | None, read_only: bool):
        tool = McpTool(
            name,
            title,
            McpToolCategory(category) if category is not None else None,
            read_only,
        )
        if tool.category is None and not read_only:
            raise ValueError("Essential tools must be read-only")
        existing = self._tools.get(name)
        if existing is not None and existing != tool:
            raise ValueError(f"Conflicting MCP tool registration: {name}")
        self._tools[name] = tool

    def get(self, name: str) -> McpTool | None:
        return self._tools.get(name)

    def allows(self, name: str, authorization: McpAuthorization | None) -> bool:
        tool = self.get(name)
        if tool is None or authorization is None:
            return False
        if authorization.access not in (McpAccess.READ_ONLY, McpAccess.READ_WRITE):
            return False
        if tool.category is None:
            return True
        access = authorization.category_access.get(tool.category)
        if access is not None and not access.read_enabled:
            return False
        return tool.read_only or (
            authorization.access == McpAccess.READ_WRITE
            and (access is None or access.write_enabled)
        )

    def metadata(self) -> dict:
        tools = tuple(self._tools.values())
        categories = []
        for category in McpToolCategory:
            read_tools = sorted(
                tool.name
                for tool in tools
                if tool.category == category and tool.read_only
            )
            write_tools = sorted(
                tool.name
                for tool in tools
                if tool.category == category and not tool.read_only
            )
            categories.append(
                {
                    "id": category.value,
                    "read_count": len(read_tools),
                    "write_count": len(write_tools),
                    "read_tools": read_tools,
                    "write_tools": write_tools,
                }
            )
        essential_tools = sorted(tool.name for tool in tools if tool.category is None)
        return {
            "tool_categories": categories,
            "essential_count": len(essential_tools),
            "essential_tools": essential_tools,
        }
