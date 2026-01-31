import abc
from typing import Optional
from uuid import UUID

from domain.entity_login import EntitySession


class SessionsPort(metaclass=abc.ABCMeta):
    async def get(self, entity_id: UUID) -> Optional[EntitySession]:
        raise NotImplementedError

    async def save(self, entity_id: UUID, session: EntitySession):
        raise NotImplementedError

    async def delete(self, entity_id: UUID):
        raise NotImplementedError
