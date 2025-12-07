import abc
from typing import Optional
from uuid import UUID

from domain.entity import Entity


class EntityPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def insert(self, entity: Entity):
        raise NotImplementedError

    @abc.abstractmethod
    def update(self, entity: Entity):
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_id(self, entity_id: UUID) -> Optional[Entity]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_all(self) -> list[Entity]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_natural_id(self, natural_id: str) -> Optional[Entity]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_name(self, name: str) -> Optional[Entity]:
        raise NotImplementedError

    @abc.abstractmethod
    def delete_by_id(self, entity_id: UUID):
        raise NotImplementedError

    @abc.abstractmethod
    def get_disabled_entities(self) -> list[Entity]:
        raise NotImplementedError
