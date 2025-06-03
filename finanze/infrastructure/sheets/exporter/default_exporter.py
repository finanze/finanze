from datetime import datetime
from typing import Optional

from application.ports.sheets_export_port import SheetsUpdatePort
from domain.exception.exceptions import NoAdapterFound
from domain.financial_entity import FinancialEntity
from domain.global_position import GlobalPosition
from domain.settings import ProductSheetConfig, SummarySheetConfig


class NullExporter(SheetsUpdatePort):
    def update_summary(
        self,
        global_positions: dict[FinancialEntity, GlobalPosition],
        config: SummarySheetConfig,
    ):
        raise NoAdapterFound("No adapter found for exporter, are credentials set up?")

    def update_sheet(
        self,
        data: object | dict[FinancialEntity, object],
        config: ProductSheetConfig,
        last_update: Optional[dict[FinancialEntity, datetime]] = None,
    ):
        raise NoAdapterFound("No adapter found for exporter, are credentials set up?")
