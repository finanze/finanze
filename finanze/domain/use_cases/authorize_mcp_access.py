import abc
from typing import Optional

from domain.mcp import McpAccess


class AuthorizeMcpAccess(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, token: Optional[str]) -> McpAccess:
        raise NotImplementedError
