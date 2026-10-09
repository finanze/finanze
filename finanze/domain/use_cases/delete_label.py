import abc
from uuid import UUID


class DeleteLabel(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, label_id: UUID):
        raise NotImplementedError
