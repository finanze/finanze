import abc

from domain.ai import AIServerInfo


class GetAIServerInfo(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, provider_id: str) -> AIServerInfo:
        raise NotImplementedError
