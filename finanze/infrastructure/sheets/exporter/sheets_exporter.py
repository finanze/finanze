from datetime import datetime
from typing import Optional

from application.ports.sheets_export_port import SheetsUpdatePort
from domain.financial_entity import FinancialEntity
from domain.global_position import GlobalPosition
from domain.settings import GoogleCredentials, ProductSheetConfig, SummarySheetConfig
from infrastructure.sheets.exporter.sheets_object_exporter import update_sheet
from infrastructure.sheets.exporter.sheets_summary_exporter import update_summary
from infrastructure.sheets.sheets_service_loader import SheetsServiceLoader


class SheetsExporter(SheetsUpdatePort):
    def __init__(self, sheets_service: SheetsServiceLoader):
        self._sheets_service = sheets_service

    def update_summary(
        self,
        global_positions: dict[FinancialEntity, GlobalPosition],
        credentials: GoogleCredentials,
        config: SummarySheetConfig,
    ):
        update_summary(
            self._sheets_service.service(credentials), global_positions, config
        )

    def update_sheet(
        self,
        data: object | dict[FinancialEntity, object],
        credentials: GoogleCredentials,
        config: ProductSheetConfig,
        last_update: Optional[dict[FinancialEntity, datetime]] = None,
    ):
        update_sheet(
            self._sheets_service.service(credentials), data, config, last_update
        )
