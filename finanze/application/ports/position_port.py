import abc
from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from domain.entity import Entity
from domain.global_position import GlobalPosition, PositionQueryRequest


class PositionPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, position: GlobalPosition):
        raise NotImplementedError

    @abc.abstractmethod
    def get_last_grouped_by_entity(
        self, query: Optional[PositionQueryRequest] = None
    ) -> Dict[Entity, GlobalPosition]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_last_updated(self, entity_id: UUID) -> Optional[datetime]:
        raise NotImplementedError
