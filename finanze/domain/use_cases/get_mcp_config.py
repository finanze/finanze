import abc

from domain.mcp import McpConfig


class GetMcpConfig(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> McpConfig:
        raise NotImplementedError
