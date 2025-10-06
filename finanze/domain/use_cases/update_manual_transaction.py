import abc

from domain.transactions import BaseTx


class UpdateManualTransaction(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, tx: BaseTx):
        raise NotImplementedError
