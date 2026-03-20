import abc
from typing import Optional
from uuid import UUID

from domain.entity_account import EntityAccount


class EntityAccountPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def create(self, account: EntityAccount) -> EntityAccount:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_entity_id(self, entity_id: UUID) -> list[EntityAccount]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_id(self, account_id: UUID) -> Optional[EntityAccount]:
        raise NotImplementedError

    @abc.abstractmethod
    async def soft_delete(self, account_id: UUID):
        raise NotImplementedError

    @abc.abstractmethod
    async def soft_delete_by_entity_id(self, entity_id: UUID):
        raise NotImplementedError
