import abc

from domain.mcp import McpConfig


class McpConfigPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get(self) -> McpConfig:
        raise NotImplementedError

    @abc.abstractmethod
    async def save(self, config: McpConfig):
        raise NotImplementedError
