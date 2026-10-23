import abc
from typing import Optional

from domain.mcp import McpAuthorization


class AuthorizeMcpAccess(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, token: Optional[str]) -> McpAuthorization:
        raise NotImplementedError
