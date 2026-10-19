import secrets

from application.ports.mcp_config_port import McpConfigPort
from domain.mcp import McpConfig, UpdateMcpConfigRequest
from domain.use_cases.update_mcp_config import UpdateMcpConfig


class UpdateMcpConfigImpl(UpdateMcpConfig):
    def __init__(self, mcp_config_port: McpConfigPort):
        self._mcp_config_port = mcp_config_port

    async def execute(self, request: UpdateMcpConfigRequest) -> McpConfig:
        current = await self._mcp_config_port.get()
        token = current.token
        if request.enabled and not token:
            token = secrets.token_urlsafe(32)

        config = McpConfig(
            enabled=request.enabled,
            read_only=request.read_only,
            token=token,
        )
        await self._mcp_config_port.save(config)
        return config
