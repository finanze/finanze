import hmac
from typing import Optional

from application.ports.datasource_initiator import DatasourceInitiator
from application.ports.mcp_config_port import McpConfigPort
from domain.mcp import McpAccess
from domain.use_cases.authorize_mcp_access import AuthorizeMcpAccess


class AuthorizeMcpAccessImpl(AuthorizeMcpAccess):
    def __init__(
        self,
        mcp_config_port: McpConfigPort,
        source_initiator: DatasourceInitiator,
    ):
        self._mcp_config_port = mcp_config_port
        self._source_initiator = source_initiator

    async def execute(self, token: Optional[str]) -> McpAccess:
        if not self._source_initiator.unlocked:
            return McpAccess.LOCKED

        config = await self._mcp_config_port.get()
        if not config.enabled or not config.token:
            return McpAccess.DISABLED

        if not token or not hmac.compare_digest(
            token.encode("utf-8"), config.token.encode("utf-8")
        ):
            return McpAccess.UNAUTHORIZED

        return McpAccess.READ_ONLY if config.read_only else McpAccess.READ_WRITE
