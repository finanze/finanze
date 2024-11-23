import abc

from domain.bank import Bank
from domain.transactions import Transactions


class TransactionPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, source: Bank, data: Transactions):
        raise NotImplementedError

    @abc.abstractmethod
    def get_all(self) -> Transactions:
        raise NotImplementedError

    @abc.abstractmethod
    def get_ids_by_source(self, source: Bank) -> set[str]:
        raise NotImplementedError
