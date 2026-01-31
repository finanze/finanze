import abc
from domain.transactions import TransactionQueryRequest, TransactionsResult


class GetTransactions(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, query: TransactionQueryRequest) -> TransactionsResult:
        pass
