import abc
from datetime import datetime

from domain.global_position import SourceType
from domain.transactions import Transactions


class TransactionPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, data: Transactions):
        raise NotImplementedError

    @abc.abstractmethod
    def get_all(self) -> Transactions:
        raise NotImplementedError

    @abc.abstractmethod
    def get_refs_by_entity(self, entity_id: int) -> set[str]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_entity(self, entity_id: int) -> Transactions:
        raise NotImplementedError

    @abc.abstractmethod
    def get_refs_by_source_type(self, real: bool) -> set[str]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_last_created_grouped_by_entity(self) -> dict[str, datetime]:
        raise NotImplementedError
