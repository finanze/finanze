import abc
from uuid import UUID

from domain.transactions import AddManualTransactionRequest


class AddManualTransaction(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: AddManualTransactionRequest) -> UUID:
        raise NotImplementedError
