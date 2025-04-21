import abc
from datetime import datetime
from typing import Optional

from domain.financial_entity import FinancialEntity
from domain.global_position import GlobalPosition


class SheetsUpdatePort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def update_summary(
            self,
            global_positions: dict[FinancialEntity, GlobalPosition],
            config: dict):
        raise NotImplementedError

    @abc.abstractmethod
    def update_sheet(
            self,
            data: object | dict[FinancialEntity, object],
            config: dict,
            last_update: Optional[dict[FinancialEntity, datetime]] = None):
        raise NotImplementedError
