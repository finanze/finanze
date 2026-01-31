import abc
from typing import Optional
from uuid import UUID

from domain.entity import Entity


class EntityPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def insert(self, entity: Entity):
        raise NotImplementedError

    @abc.abstractmethod
    async def update(self, entity: Entity):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_id(self, entity_id: UUID) -> Optional[Entity]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_all(self) -> list[Entity]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_natural_id(self, natural_id: str) -> Optional[Entity]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_name(self, name: str) -> Optional[Entity]:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_by_id(self, entity_id: UUID):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_disabled_entities(self) -> list[Entity]:
        raise NotImplementedError
