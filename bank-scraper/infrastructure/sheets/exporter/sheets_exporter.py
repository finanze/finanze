from datetime import datetime
from typing import Optional

from application.ports.sheets_export_port import SheetsUpdatePort
from domain.financial_entity import FinancialEntity
from domain.global_position import GlobalPosition
from infrastructure.sheets.exporter.sheets_object_exporter import update_sheet
from infrastructure.sheets.exporter.sheets_summary_exporter import update_summary
from infrastructure.sheets.sheets_base_loader import spreadsheets


class SheetsExporter(SheetsUpdatePort):

    def __init__(self):
        self._sheet = spreadsheets()

    def update_summary(
            self,
            global_positions: dict[FinancialEntity, GlobalPosition],
            config: dict):
        update_summary(self._sheet, global_positions, config)

    def update_sheet(
            self,
            data: object | dict[FinancialEntity, object],
            config: dict,
            last_update: Optional[dict[FinancialEntity, datetime]] = None):
        update_sheet(self._sheet, data, config, last_update)
