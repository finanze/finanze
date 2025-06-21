import abc
from datetime import datetime
from uuid import UUID

from domain.entity import Entity
from domain.transactions import Transactions, TransactionQueryRequest, BaseTx


class TransactionPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, data: Transactions):
        raise NotImplementedError

    @abc.abstractmethod
    def get_all(self) -> Transactions:
        raise NotImplementedError

    @abc.abstractmethod
    def get_refs_by_entity(self, entity_id: UUID) -> set[str]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_entity(self, entity_id: UUID) -> Transactions:
        raise NotImplementedError

    @abc.abstractmethod
    def get_refs_by_source_type(self, real: bool) -> set[str]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_last_created_grouped_by_entity(self) -> dict[Entity, datetime]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_filters(self, query: TransactionQueryRequest) -> list[BaseTx]:
        raise NotImplementedError
