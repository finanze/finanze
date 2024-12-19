import os.path
from datetime import datetime
from typing import Union, Optional

from application.ports.sheets_export_port import SheetsUpdatePort
from domain.global_position import GlobalPosition
from infrastructure.sheets.exporter.sheets_object_exporter import update_sheet
from infrastructure.sheets.exporter.sheets_summary_exporter import update_summary
from infrastructure.sheets.sheets_base_loader import spreadsheets


class SheetsExporter(SheetsUpdatePort):

    def __init__(self):
        self.__sheet_id = os.environ["WRITE_SHEETS_IDS"]
        self.__sheet = spreadsheets()

    def update_summary(
            self,
            global_positions: dict[str, GlobalPosition],
            sheet_name: str):
        update_summary(self.__sheet, global_positions, self.__sheet_id, sheet_name)

    def update_sheet(
            self,
            data: Union[object, dict[str, object]],
            sheet_name: str,
            field_paths: list[str],
            last_update: Optional[dict[str, datetime]] = None):
        update_sheet(self.__sheet, data, self.__sheet_id, sheet_name, field_paths, last_update)
