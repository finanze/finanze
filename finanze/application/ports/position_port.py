import abc
from typing import Optional

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
