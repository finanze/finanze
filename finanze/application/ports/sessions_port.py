import abc
from typing import Optional
from uuid import UUID

from domain.login import EntitySession


class SessionsPort(metaclass=abc.ABCMeta):

    def get(self, entity_id: UUID) -> Optional[EntitySession]:
        raise NotImplementedError

    def save(self, entity_id: UUID, session: EntitySession):
        raise NotImplementedError

    def delete(self, entity_id: UUID):
        raise NotImplementedError
