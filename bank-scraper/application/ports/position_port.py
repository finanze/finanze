import abc
from datetime import datetime
from typing import Optional

from domain.financial_entity import FinancialEntity
from domain.global_position import GlobalPosition


class PositionPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, entity: str, position: GlobalPosition):
        raise NotImplementedError

    @abc.abstractmethod
    def get_last_grouped_by_entity(self) -> dict[str, GlobalPosition]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_last_updated(self, entity: FinancialEntity) -> Optional[datetime]:
        raise NotImplementedError
