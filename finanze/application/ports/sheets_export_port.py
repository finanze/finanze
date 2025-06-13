import abc
from datetime import datetime
from typing import Optional

from domain.financial_entity import FinancialEntity
from domain.global_position import GlobalPosition
from domain.settings import GoogleCredentials, ProductSheetConfig, SummarySheetConfig


class SheetsUpdatePort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def update_summary(
        self,
        global_positions: dict[FinancialEntity, GlobalPosition],
        credentials: GoogleCredentials,
        config: SummarySheetConfig,
    ):
        raise NotImplementedError

    @abc.abstractmethod
    def update_sheet(
        self,
        data: object | dict[FinancialEntity, object],
        credentials: GoogleCredentials,
        config: ProductSheetConfig,
        last_update: Optional[dict[FinancialEntity, datetime]] = None,
    ):
        raise NotImplementedError
