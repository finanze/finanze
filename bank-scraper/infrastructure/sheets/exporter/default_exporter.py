from datetime import datetime
from typing import Union, Optional

from application.ports.sheets_export_port import SheetsUpdatePort
from domain.exception.exceptions import NoAdapterFound
from domain.financial_entity import FinancialEntity
from domain.global_position import GlobalPosition


class NullExporter(SheetsUpdatePort):

    def update_summary(
            self,
            global_positions: dict[FinancialEntity, GlobalPosition],
            config: dict):
        raise NoAdapterFound("No adapter found for exporter, are credentials set up?")

    def update_sheet(
            self,
            data: Union[object, dict[FinancialEntity, object]],
            config: dict,
            last_update: Optional[dict[FinancialEntity, datetime]] = None):
        raise NoAdapterFound("No adapter found for exporter, are credentials set up?")
