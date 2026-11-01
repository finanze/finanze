import secrets

from application.ports.mcp_config_port import McpConfigPort
from domain.mcp import McpConfig
from domain.use_cases.regenerate_mcp_token import RegenerateMcpToken


class RegenerateMcpTokenImpl(RegenerateMcpToken):
    def __init__(self, mcp_config_port: McpConfigPort):
        self._mcp_config_port = mcp_config_port

    async def execute(self) -> McpConfig:
        current = await self._mcp_config_port.get()
        config = McpConfig(
            enabled=current.enabled,
            read_only=current.read_only,
            token=secrets.token_urlsafe(32),
            category_access=current.category_access,
        )
        await self._mcp_config_port.save(config)
        return config
