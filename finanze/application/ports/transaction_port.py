import abc
from datetime import datetime
from uuid import UUID

from domain.financial_entity import FinancialEntity
from domain.transactions import Transactions


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
    def get_last_created_grouped_by_entity(self) -> dict[FinancialEntity, datetime]:
        raise NotImplementedError
