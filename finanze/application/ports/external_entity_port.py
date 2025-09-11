import abc
from typing import Optional
from uuid import UUID

from domain.external_entity import (
    ExternalEntity,
    ExternalEntityStatus,
)


class ExternalEntityPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def upsert(self, ee: ExternalEntity):
        raise NotImplementedError

    @abc.abstractmethod
    def update_status(self, ee_id: UUID, status: ExternalEntityStatus):
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_id(self, ee_id: UUID) -> Optional[ExternalEntity]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_entity_id(self, entity_id: UUID) -> Optional[ExternalEntity]:
        raise NotImplementedError

    @abc.abstractmethod
    def delete_by_id(self, ee_id: UUID):
        raise NotImplementedError
