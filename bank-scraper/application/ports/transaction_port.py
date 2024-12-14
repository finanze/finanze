import abc
from datetime import datetime

from domain.financial_entity import Entity
from domain.global_position import SourceType
from domain.transactions import Transactions, TxProductType


class TransactionPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, data: Transactions) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_all(self) -> Transactions:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_product(self, product_types: list[TxProductType]) -> Transactions:
        raise NotImplementedError

    @abc.abstractmethod
    def get_ids_by_entity(self, entity: str) -> set[str]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_ids_by_source_type(self, source_type: SourceType) -> set[str]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_last_created_grouped_by_entity(self) -> dict[str, datetime]:
        raise NotImplementedError
