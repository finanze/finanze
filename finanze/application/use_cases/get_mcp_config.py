from application.ports.mcp_config_port import McpConfigPort
from domain.mcp import McpConfig
from domain.use_cases.get_mcp_config import GetMcpConfig


class GetMcpConfigImpl(GetMcpConfig):
    def __init__(self, mcp_config_port: McpConfigPort):
        self._mcp_config_port = mcp_config_port

    async def execute(self) -> McpConfig:
        return await self._mcp_config_port.get()
