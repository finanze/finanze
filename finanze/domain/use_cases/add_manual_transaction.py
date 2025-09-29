import abc
from uuid import UUID

from domain.transactions import BaseTx


class AddManualTransaction(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, tx: BaseTx) -> UUID:
        raise NotImplementedError
