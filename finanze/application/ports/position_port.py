import abc
from datetime import datetime
from typing import Optional, Dict
from uuid import UUID

from domain.financial_entity import FinancialEntity
from domain.global_position import GlobalPosition, PositionQueryRequest


class PositionPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, position: GlobalPosition):
        raise NotImplementedError

    @abc.abstractmethod
    def get_last_grouped_by_entity(self, query: PositionQueryRequest) -> Dict[FinancialEntity, GlobalPosition]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_last_updated(self, entity_id: UUID) -> Optional[datetime]:
        raise NotImplementedError
