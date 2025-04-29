import abc
from typing import Optional
from uuid import UUID

from domain.financial_entity import FinancialEntity


class EntityPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def insert(self, entity: FinancialEntity):
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_id(self, entity_id: UUID) -> Optional[FinancialEntity]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_all(self) -> list[FinancialEntity]:
        raise NotImplementedError

    @abc.abstractmethod
    def delete_by_id(self, entity_id: UUID):
        raise NotImplementedError
