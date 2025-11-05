import abc
from typing import Optional
from uuid import UUID

from domain.fetch_record import DataSource
from domain.transactions import BaseTx, TransactionQueryRequest, Transactions


class TransactionPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, data: Transactions):
        raise NotImplementedError

    @abc.abstractmethod
    def get_all(
        self,
        real: Optional[bool] = None,
        excluded_entities: Optional[list[UUID]] = None,
    ) -> Transactions:
        raise NotImplementedError

    @abc.abstractmethod
    def get_refs_by_entity(self, entity_id: UUID) -> set[str]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_entity(self, entity_id: UUID) -> Transactions:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_entity_and_source(
        self, entity_id: UUID, source: DataSource
    ) -> Transactions:
        raise NotImplementedError

    @abc.abstractmethod
    def get_refs_by_source_type(self, real: bool) -> set[str]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_filters(self, query: TransactionQueryRequest) -> list[BaseTx]:
        raise NotImplementedError

    @abc.abstractmethod
    def delete_by_source(self, source: DataSource):
        raise NotImplementedError

    @abc.abstractmethod
    def delete_by_entity_source(self, entity_id: UUID, source: DataSource):
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_id(self, tx_id: UUID) -> Optional[BaseTx]:
        raise NotImplementedError

    @abc.abstractmethod
    def delete_by_id(self, tx_id: UUID):
        raise NotImplementedError
