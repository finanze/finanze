import abc
from uuid import UUID


class DeletePeriodicFlow(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, flow_id: UUID):
        raise NotImplementedError
