import abc
import datetime
from typing import Optional
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
    ) -> dict[Entity, GlobalPosition]:
        raise NotImplementedError

    @abc.abstractmethod
    def delete_position_for_date(
        self, entity_id: UUID, date: datetime.date, is_real: bool
    ):
        raise NotImplementedError
