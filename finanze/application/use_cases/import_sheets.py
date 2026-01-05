import logging
from asyncio import Lock
from datetime import datetime
from uuid import UUID, uuid4

from application.ports.config_port import ConfigPort
from application.ports.entity_port import EntityPort
from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.position_port import PositionPort
from application.ports.sheets_port import SheetsPort
from application.ports.template_parser_port import TemplateParserPort
from application.ports.template_port import TemplatePort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_port import TransactionPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from dateutil.tz import tzlocal
from domain.entity import Feature
from domain.exception.exceptions import (
    ExecutionConflict,
    ExternalIntegrationRequired,
    SheetNotFound,
)
from domain.export import SheetParams, NumberFormat
from domain.external_integration import (
    ExternalIntegrationId,
    ExternalIntegrationPayload,
)
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.importing import (
    ImportCandidate,
    ImportedData,
    ImportError,
    ImportErrorType,
    ImportResult,
    ImportResultCode,
    TemplatedDataParserParams,
)
from domain.settings import ImportSheetConfig, SheetsGlobalConfig, SheetsImportConfig
from domain.use_cases.import_sheets import ImportSheets
from domain.virtual_data import VirtualDataImport, VirtualDataSource

DEFAULT_DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"
DEFAULT_DATE_FORMAT = "%d/%m/%Y"


def _map_sheet_params(
    config: ImportSheetConfig,
    global_config: SheetsGlobalConfig,
) -> SheetParams:
    return SheetParams(
        range=config.range,
        spreadsheet_id=config.spreadsheetId or global_config.spreadsheetId,
    )


class ImportSheetsImpl(ImportSheets):
    def __init__(
        self,
        position_port: PositionPort,
        transaction_port: TransactionPort,
        sheets_port: SheetsPort,
        entity_port: EntityPort,
        external_integration_port: ExternalIntegrationPort,
        config_port: ConfigPort,
        virtual_import_registry: VirtualImportRegistry,
        template_port: TemplatePort,
        template_parser: TemplateParserPort,
        transaction_handler_port: TransactionHandlerPort,
    ):
        self._position_port = position_port
        self._transaction_port = transaction_port
        self._sheets_port = sheets_port
        self._entity_port = entity_port
        self._external_integration_port = external_integration_port
        self._config_port = config_port
        self._virtual_import_registry = virtual_import_registry
        self._template_port = template_port
        self._template_parser = template_parser
        self._transaction_handler_port = transaction_handler_port

        self._lock = Lock()

        self._log = logging.getLogger(__name__)

    async def execute(self) -> ImportResult:
        config = await self._config_port.load()
        sheets_import_config = config.importing.sheets

        sheets_credentials = await self._external_integration_port.get_payload(
            ExternalIntegrationId.GOOGLE_SHEETS
        )
        if not sheets_credentials:
            raise ExternalIntegrationRequired([ExternalIntegrationId.GOOGLE_SHEETS])

        if not sheets_import_config or (
            not sheets_import_config.position and not sheets_import_config.transactions
        ):
            return ImportResult(ImportResultCode.DISABLED)

        if self._lock.locked():
            raise ExecutionConflict()

        async with self._lock:
            existing_entities = await self._entity_port.get_all()
            existing_entities_by_name = {
                entity.name: entity for entity in existing_entities
            }

            (
                position_candidates,
                position_sheet_errors,
            ) = await self._get_import_candidates(
                Feature.POSITION, sheets_credentials, sheets_import_config
            )

            import_position_result = await self._template_parser.global_positions(
                position_candidates, existing_entities_by_name
            )

            async with self._transaction_handler_port.start():
                now = datetime.now(tzlocal())
                import_id = uuid4()
                virtual_import_entries = []
                if import_position_result.positions:
                    for entity in import_position_result.created_entities:
                        await self._entity_port.insert(entity)
                        existing_entities_by_name[entity.name] = entity

                    for position in import_position_result.positions:
                        await self._position_port.save(position)
                        virtual_import_entries.append(
                            VirtualDataImport(
                                import_id=import_id,
                                global_position_id=position.id,
                                source=VirtualDataSource.SHEETS,
                                date=now,
                                feature=Feature.POSITION,
                                entity_id=position.entity.id,
                            )
                        )

                tx_candidates, tx_sheet_errors = await self._get_import_candidates(
                    Feature.TRANSACTIONS, sheets_credentials, sheets_import_config
                )

                imported_txs = await self._template_parser.transactions(
                    tx_candidates, existing_entities_by_name
                )

                await self._transaction_port.delete_by_source(DataSource.SHEETS)
                transactions = imported_txs.transactions
                if transactions:
                    for entity in imported_txs.created_entities:
                        await self._entity_port.insert(entity)

                    await self._transaction_port.save(transactions)

                    tx_entities = {
                        tx.entity.id
                        for tx in transactions.investment + transactions.account
                    }
                    for entity_id in tx_entities:
                        virtual_import_entries.append(
                            VirtualDataImport(
                                import_id=import_id,
                                global_position_id=None,
                                source=VirtualDataSource.SHEETS,
                                date=now,
                                feature=Feature.TRANSACTIONS,
                                entity_id=entity_id,
                            )
                        )

                if not virtual_import_entries:
                    virtual_import_entries.append(
                        VirtualDataImport(
                            import_id=import_id,
                            global_position_id=None,
                            source=VirtualDataSource.SHEETS,
                            date=now,
                            feature=None,
                            entity_id=None,
                        )
                    )

                await self._virtual_import_registry.insert(virtual_import_entries)

                errors = (
                    position_sheet_errors
                    + tx_sheet_errors
                    + import_position_result.errors
                    + imported_txs.errors
                )
                data = ImportedData(
                    positions=import_position_result.positions,
                    transactions=transactions,
                )

                return ImportResult(
                    ImportResultCode.COMPLETED,
                    data=data,
                    errors=errors,
                )

    async def _get_import_candidates(
        self,
        feature: Feature,
        sheets_credentials: ExternalIntegrationPayload,
        virtual_fetch_config: SheetsImportConfig,
    ) -> tuple[list[ImportCandidate], list[ImportError]]:
        candidates = []
        errors = []
        config_entries = (
            virtual_fetch_config.transactions
            if feature == Feature.TRANSACTIONS
            else virtual_fetch_config.position
        ) or []

        for config in config_entries:
            sheets_params = _map_sheet_params(config, virtual_fetch_config.globals)
            try:
                table = await self._sheets_port.read(sheets_credentials, sheets_params)
            except SheetNotFound:
                errors.append(
                    ImportError(
                        type=ImportErrorType.SHEET_NOT_FOUND,
                        entry=config.range,
                    )
                )
                self._log.warning(f"Sheet {config.range} not found")
                continue

            parser_params = await self._map_template_params(
                feature,
                config,
                virtual_fetch_config.globals,
            )

            candidates.append(
                ImportCandidate(
                    name=config.range,
                    source=DataSource.SHEETS,
                    params=parser_params,
                    data=table,
                )
            )
        return candidates, errors

    async def _map_template_params(
        self,
        feature: Feature,
        config: ImportSheetConfig,
        global_config: SheetsGlobalConfig,
    ) -> TemplatedDataParserParams:
        template = await self._template_port.get_by_id(UUID(config.template.id))

        return TemplatedDataParserParams(
            template=template,
            number_format=NumberFormat.EUROPEAN,
            feature=feature,
            product=ProductType(config.data),
            datetime_format=config.datetimeFormat
            or global_config.datetimeFormat
            or DEFAULT_DATETIME_FORMAT,
            date_format=config.dateFormat
            or global_config.dateFormat
            or DEFAULT_DATE_FORMAT,
            params={},
        )
