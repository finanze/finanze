import abc
from uuid import UUID

from domain.transactions import BaseTx, TransactionQueryRequest, Transactions


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
    def get_by_filters(self, query: TransactionQueryRequest) -> list[BaseTx]:
        raise NotImplementedError

    @abc.abstractmethod
    def delete_non_real(self):
        raise NotImplementedError

    @abc.abstractmethod
    def delete_for_real_entity(self, entity_id: UUID):
        raise NotImplementedError
