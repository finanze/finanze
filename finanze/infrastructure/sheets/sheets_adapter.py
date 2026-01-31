import logging

from application.ports.sheets_port import SheetsPort
from domain.exception.exceptions import SheetNotFound
from domain.export import SheetParams
from domain.external_integration import ExternalIntegrationPayload
from googleapiclient.errors import HttpError
from infrastructure.sheets.sheets_service_loader import SheetsServiceLoader


class SheetsAdapter(SheetsPort):
    def __init__(self, sheets_service_loader: SheetsServiceLoader):
        self._sheets_service_loader = sheets_service_loader

        self._log = logging.getLogger(__name__)

    async def update(
        self,
        table: list[list[str]],
        credentials: ExternalIntegrationPayload,
        params: SheetParams,
    ):
        sheets_service = self._sheets_service_loader.service(credentials)

        sheet_id = params.spreadsheet_id
        sheet_range = params.range

        for row in table:
            row.extend(["" for _ in range(10)])

        rows = [
            *table,
            *[["" for _ in range(100)] for _ in range(1000)],
        ]

        request = sheets_service.values().update(
            spreadsheetId=sheet_id,
            range=f"{sheet_range}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": rows},
        )

        request.execute()

    async def read(
        self, credentials: ExternalIntegrationPayload, params: SheetParams
    ) -> list[list[str]]:
        sheet_id = params.spreadsheet_id
        sheet_range = params.range

        sheets_service = self._sheets_service_loader.service(credentials)
        try:
            result = (
                sheets_service.values()
                .get(spreadsheetId=sheet_id, range=sheet_range)
                .execute()
            )
        except HttpError as e:
            if e.status_code == 400:
                raise SheetNotFound()
            else:
                raise

        return result.get("values", [])
