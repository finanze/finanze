import abc
from uuid import UUID


class DeleteManualTransaction(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, tx_id: UUID):
        raise NotImplementedError
