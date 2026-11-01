import abc

from domain.mcp import McpConfig, UpdateMcpConfigRequest


class UpdateMcpConfig(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: UpdateMcpConfigRequest) -> McpConfig:
        raise NotImplementedError
