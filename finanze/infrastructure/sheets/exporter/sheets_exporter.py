from datetime import datetime
from typing import Optional

from application.ports.sheets_export_port import SheetsUpdatePort
from domain.entity import Entity
from domain.external_integration import ExternalIntegrationPayload
from domain.settings import ProductSheetConfig
from infrastructure.sheets.exporter.sheets_object_exporter import update_sheet
from infrastructure.sheets.sheets_service_loader import SheetsServiceLoader


class SheetsExporter(SheetsUpdatePort):
    def __init__(self, sheets_service: SheetsServiceLoader):
        self._sheets_service = sheets_service

    def update_sheet(
        self,
        data: object | dict[Entity, object],
        credentials: ExternalIntegrationPayload,
        config: ProductSheetConfig,
        last_update: Optional[dict[Entity, datetime]] = None,
    ):
        update_sheet(
            self._sheets_service.service(credentials), data, config, last_update
        )
