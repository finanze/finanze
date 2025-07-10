import abc
from typing import Optional
from uuid import UUID

from domain.entity import Entity


class EntityPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def insert(self, entity: Entity):
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_id(self, entity_id: UUID) -> Optional[Entity]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_all(self) -> list[Entity]:
        raise NotImplementedError

    @abc.abstractmethod
    def delete_by_id(self, entity_id: UUID):
        raise NotImplementedError
