import abc
from uuid import UUID


class RestoreRecurringMovement(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, ignored_id: UUID):
        raise NotImplementedError
