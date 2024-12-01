import abc
from datetime import datetime

from domain.bank import Bank
from domain.transactions import Transactions, TxProductType


class TransactionPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, source: Bank, data: Transactions):
        raise NotImplementedError

    @abc.abstractmethod
    def get_all(self) -> Transactions:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_product(self, product_types: list[TxProductType]) -> Transactions:
        raise NotImplementedError

    @abc.abstractmethod
    def get_ids_by_source(self, source: Bank) -> set[str]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_last_created_grouped_by_source(self) -> dict[str, datetime]:
        raise NotImplementedError
