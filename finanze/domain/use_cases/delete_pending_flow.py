import abc
from uuid import UUID


class DeletePendingFlow(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, flow_id: UUID):
        raise NotImplementedError
