import abc

from domain.local_model import LocalModelRequest


class DeleteLocalModel(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: LocalModelRequest):
        raise NotImplementedError
