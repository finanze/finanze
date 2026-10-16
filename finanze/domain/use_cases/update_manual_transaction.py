import abc

from domain.transactions import UpdateManualTransactionRequest


class UpdateManualTransaction(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: UpdateManualTransactionRequest):
        raise NotImplementedError
