from asyncio import Lock
from datetime import datetime
from typing import Optional
from uuid import UUID

from application.ports.auto_contributions_port import AutoContributionsPort
from application.ports.config_port import ConfigPort
from application.ports.entity_port import EntityPort
from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.historic_port import HistoricPort
from application.ports.last_fetches_port import LastFetchesPort
from application.ports.position_port import PositionPort
from application.ports.sheets_port import SheetsPort
from application.ports.template_port import TemplatePort
from application.ports.template_processor_port import TemplateProcessorPort
from application.ports.transaction_port import TransactionPort
from dateutil.tz import tzlocal
from domain.auto_contributions import ContributionQueryRequest
from domain.entity import Entity, Feature
from domain.exception.exceptions import ExecutionConflict, ExternalIntegrationRequired
from domain.export import SheetParams, TemplatedDataProcessorParams, NumberFormat
from domain.external_integration import (
    ExternalIntegrationId,
    ExternalIntegrationPayload,
)
from domain.fetch_record import FetchRecord
from domain.global_position import PositionQueryRequest, ProductType
from domain.historic import HistoricQueryRequest
from domain.settings import (
    ExportSheetConfig,
    SheetsGlobalConfig,
)
from domain.template import ProcessorDataFilter
from domain.use_cases.export_sheets import ExportSheets
from pytz import utc


def _format_datetime(value, params: TemplatedDataProcessorParams):
    datetime_format = params.datetime_format
    value = value.replace(tzinfo=utc).astimezone(tzlocal())
    if not datetime_format:
        return value.isoformat()
    return value.strftime(datetime_format)


def _map_last_update_row(
    last_update: dict[Entity, datetime], params: TemplatedDataProcessorParams
) -> list[str]:
    last_update = sorted(last_update.items(), key=lambda item: item[1], reverse=True)
    last_update_row = []
    for k, v in last_update:
        last_update_row.append(str(k))
        last_update_date = v.astimezone(tz=tzlocal())
        formated_last_update_date = _format_datetime(last_update_date, params)
        last_update_row.append(formated_last_update_date)

    last_update_row.extend(["" for _ in range(10)])
    return last_update_row


def _map_top_row(
    params: TemplatedDataProcessorParams,
    last_update: Optional[dict[Entity, datetime]] = None,
) -> list[str]:
    if last_update:
        return _map_last_update_row(last_update, params)
    else:
        last_update_date = datetime.now(tzlocal())
        return [_format_datetime(last_update_date, params)]


def _map_last_fetch(last_fetches: dict[Entity, FetchRecord]) -> dict[Entity, datetime]:
    return {e: f.date for e, f in last_fetches.items()}


def _map_sheet_params(
    config: ExportSheetConfig,
    global_config: SheetsGlobalConfig,
) -> SheetParams:
    return SheetParams(
        range=config.range,
        spreadsheet_id=config.spreadsheetId or global_config.spreadsheetId,
    )


class ExportSheetsImpl(ExportSheets):
    def __init__(
        self,
        position_port: PositionPort,
        auto_contr_port: AutoContributionsPort,
        transaction_port: TransactionPort,
        historic_port: HistoricPort,
        sheets_port: SheetsPort,
        last_fetches_port: LastFetchesPort,
        external_integration_port: ExternalIntegrationPort,
        entity_port: EntityPort,
        template_port: TemplatePort,
        template_processor: TemplateProcessorPort,
        config_port: ConfigPort,
    ):
        self._position_port = position_port
        self._auto_contr_port = auto_contr_port
        self._transaction_port = transaction_port
        self._historic_port = historic_port
        self._sheets_port = sheets_port
        self._last_fetches_port = last_fetches_port
        self._external_integration_port = external_integration_port
        self._entity_port = entity_port
        self._template_port = template_port
        self._template_processor = template_processor
        self._config_port = config_port

        self._lock = Lock()

    async def execute(self):
        config = self._config_port.load()
        sheets_export_config = config.export.sheets

        sheet_credentials = self._external_integration_port.get_payload(
            ExternalIntegrationId.GOOGLE_SHEETS
        )

        if not sheets_export_config or not sheet_credentials:
            raise ExternalIntegrationRequired([ExternalIntegrationId.GOOGLE_SHEETS])

        if not (
            sheets_export_config.transactions
            or sheets_export_config.position
            or sheets_export_config.contributions
            or sheets_export_config.historic
        ):
            return

        config_globals = sheets_export_config.globals
        if not config_globals:
            return

        if self._lock.locked():
            raise ExecutionConflict()

        async with self._lock:
            disabled_entities = [
                e.id for e in self._entity_port.get_disabled_entities()
            ]
            global_position_by_entity = self._position_port.get_last_grouped_by_entity(
                PositionQueryRequest(excluded_entities=disabled_entities)
            )
            self.update(
                Feature.POSITION,
                list(global_position_by_entity.values()),
                config_globals,
                sheets_export_config.position,
                sheet_credentials,
            )

            auto_contributions = self._auto_contr_port.get_all_grouped_by_entity(
                ContributionQueryRequest(excluded_entities=disabled_entities)
            )
            self.update(
                Feature.AUTO_CONTRIBUTIONS,
                list(auto_contributions.values()),
                config_globals,
                sheets_export_config.contributions,
                sheet_credentials,
            )

            transactions = self._transaction_port.get_all(
                excluded_entities=disabled_entities
            )
            self.update(
                Feature.TRANSACTIONS,
                transactions.account + transactions.investment,
                config_globals,
                sheets_export_config.transactions,
                sheet_credentials,
            )

            historic = self._historic_port.get_by_filters(
                HistoricQueryRequest(excluded_entities=disabled_entities)
            )
            self.update(
                Feature.HISTORIC,
                historic.entries,
                config_globals,
                sheets_export_config.historic,
                sheet_credentials,
            )

    def update(
        self,
        feature: Feature,
        data: list,
        global_config: SheetsGlobalConfig,
        config_entries: list[ExportSheetConfig],
        credentials: ExternalIntegrationPayload,
    ):
        for config in config_entries:
            products = None
            if config.data is not None:
                products = [ProductType(field) for field in config.data]

            sheets_params = _map_sheet_params(config, global_config)
            params = self._map_template_params(feature, config, global_config, products)

            table = []
            if config.lastUpdate:
                table = [_map_top_row(params)]

            table.extend(
                self._template_processor.process(
                    data,
                    params,
                )
            )
            self._sheets_port.update(table, credentials, sheets_params)

    def _map_template_params(
        self,
        feature: Feature,
        config: ExportSheetConfig,
        global_config: SheetsGlobalConfig,
        products: Optional[list[ProductType]] = None,
    ) -> TemplatedDataProcessorParams:
        template = None
        if config.template:
            template = self._template_port.get_by_id(UUID(config.template.id))

        filters = [
            ProcessorDataFilter(
                field=filter_config.field,
                values=filter_config.values,
            )
            for filter_config in (config.filters or [])
        ]

        return TemplatedDataProcessorParams(
            template=template,
            number_format=NumberFormat.EUROPEAN,
            feature=feature,
            products=products,
            datetime_format=config.datetimeFormat or global_config.datetimeFormat,
            date_format=config.dateFormat or global_config.dateFormat,
            filters=filters,
        )
