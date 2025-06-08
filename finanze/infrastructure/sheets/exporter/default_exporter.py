from datetime import datetime
from typing import Optional

from application.ports.sheets_export_port import SheetsUpdatePort
from domain.exception.exceptions import NoAdapterFound
from domain.financial_entity import FinancialEntity
from domain.global_position import GlobalPosition
from domain.settings import ProductSheetConfig, SummarySheetConfig, GoogleCredentials


class NullExporter(SheetsUpdatePort):
    def update_summary(
        self,
        global_positions: dict[FinancialEntity, GlobalPosition],
        credentials: GoogleCredentials,
        config: SummarySheetConfig,
    ):
        raise NoAdapterFound("No adapter found for exporter, are credentials set up?")

    def update_sheet(
        self,
        data: object | dict[FinancialEntity, object],
        credentials: GoogleCredentials,
        config: ProductSheetConfig,
        last_update: Optional[dict[FinancialEntity, datetime]] = None,
    ):
        raise NoAdapterFound("No adapter found for exporter, are credentials set up?")
