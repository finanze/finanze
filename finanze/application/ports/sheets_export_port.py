import abc
from datetime import datetime
from typing import Optional

from domain.financial_entity import FinancialEntity
from domain.global_position import GlobalPosition
from domain.settings import SummarySheetConfig, ProductSheetConfig


class SheetsUpdatePort(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def update_summary(
            self,
            global_positions: dict[FinancialEntity, GlobalPosition],
            config: SummarySheetConfig):
        raise NotImplementedError

    @abc.abstractmethod
    def update_sheet(
            self,
            data: object | dict[FinancialEntity, object],
            config: ProductSheetConfig,
            last_update: Optional[dict[FinancialEntity, datetime]] = None):
        raise NotImplementedError
