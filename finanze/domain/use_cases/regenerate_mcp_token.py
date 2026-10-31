import abc

from domain.mcp import McpConfig


class RegenerateMcpToken(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> McpConfig:
        raise NotImplementedError
