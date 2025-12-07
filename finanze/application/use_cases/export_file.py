from asyncio import Lock
from datetime import datetime
from typing import Optional
from uuid import UUID

from application.ports.auto_contributions_port import AutoContributionsPort
from application.ports.entity_port import EntityPort
from application.ports.file_rw_port import TableRWPort
from application.ports.historic_port import HistoricPort
from application.ports.position_port import PositionPort
from application.ports.template_port import TemplatePort
from application.ports.template_processor_port import TemplateProcessorPort
from application.ports.transaction_port import TransactionPort
from dateutil.tz import tzlocal
from domain.auto_contributions import ContributionQueryRequest
from domain.entity import Feature
from domain.exception.exceptions import ExecutionConflict, ExportException
from domain.export import (
    FileExportRequest,
    FileExportResult,
    FileFormat,
    TemplatedDataProcessorParams,
)
from domain.global_position import PositionQueryRequest
from domain.historic import HistoricQueryRequest
from domain.use_cases.export_file import ExportFile


def _content_type_for_format(export_format: FileFormat) -> str:
    if export_format == FileFormat.CSV:
        return "text/csv"
    if export_format == FileFormat.TSV:
        return "text/tab-separated-values"
    if export_format == FileFormat.XLSX:
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    raise ValueError(f"Unsupported export format: {export_format}")


class ExportFileImpl(ExportFile):
    def __init__(
        self,
        position_port: PositionPort,
        auto_contr_port: AutoContributionsPort,
        transaction_port: TransactionPort,
        historic_port: HistoricPort,
        entity_port: EntityPort,
        template_port: TemplatePort,
        template_processor: TemplateProcessorPort,
        table_rw_port: TableRWPort,
    ):
        self._position_port = position_port
        self._auto_contr_port = auto_contr_port
        self._transaction_port = transaction_port
        self._historic_port = historic_port
        self._entity_port = entity_port
        self._template_port = template_port
        self._template_processor = template_processor
        self._table_rw_port = table_rw_port
        self._lock = Lock()

    async def execute(self, request: FileExportRequest) -> FileExportResult:
        if self._lock.locked():
            raise ExecutionConflict()

        async with self._lock:
            rows = self._build_rows(request)
            if not rows:
                raise ExportException("No data available for export")

            timestamp = datetime.now(tzlocal()).strftime("%Y%m%d_%H%M%S")
            filename = f"export_{request.feature.lower()}_{timestamp}.{request.format.name.lower()}"

            content_type = _content_type_for_format(request.format)

            data = self._table_rw_port.convert(rows, request.format)

            return FileExportResult(
                filename=filename,
                content_type=content_type,
                data=data,
                size=len(data),
            )

    def _build_rows(self, request: FileExportRequest) -> list[list[str]]:
        feature = request.feature
        products = request.data or []
        disabled_entities = [e.id for e in self._entity_port.get_disabled_entities()]
        template = self._resolve_template(request.template)

        if feature == Feature.POSITION:
            return self._build_position_rows(
                products, disabled_entities, template, request
            )
        if feature == Feature.AUTO_CONTRIBUTIONS:
            return self._build_auto_contribution_rows(
                disabled_entities, template, request
            )
        if feature == Feature.TRANSACTIONS:
            return self._build_transaction_rows(
                products, disabled_entities, template, request
            )
        if feature == Feature.HISTORIC:
            return self._build_historic_rows(
                products, disabled_entities, template, request
            )
        raise ExportException(f"Unsupported feature: {feature}")

    def _build_position_rows(self, products, disabled_entities, template, request):
        positions = self._position_port.get_last_grouped_by_entity(
            PositionQueryRequest(excluded_entities=disabled_entities)
        )
        data = list(positions.values())
        params = TemplatedDataProcessorParams(
            template=template,
            number_format=request.number_format,
            feature=Feature.POSITION,
            products=products,
            datetime_format=request.datetime_format,
            date_format=request.date_format,
        )
        return self._template_processor.process(data, params)

    def _build_auto_contribution_rows(self, disabled_entities, template, request):
        contributions = self._auto_contr_port.get_all_grouped_by_entity(
            ContributionQueryRequest(excluded_entities=disabled_entities)
        )
        data = list(contributions.values())
        params = TemplatedDataProcessorParams(
            template=template,
            number_format=request.number_format,
            feature=Feature.AUTO_CONTRIBUTIONS,
            products=None,
            datetime_format=request.datetime_format,
            date_format=request.date_format,
        )
        return self._template_processor.process(data, params)

    def _build_transaction_rows(self, products, disabled_entities, template, request):
        txs = self._transaction_port.get_all(excluded_entities=disabled_entities)
        data = txs.account + txs.investment
        params = TemplatedDataProcessorParams(
            template=template,
            number_format=request.number_format,
            feature=Feature.TRANSACTIONS,
            products=products,
            datetime_format=request.datetime_format,
            date_format=request.date_format,
        )
        return self._template_processor.process(data, params)

    def _build_historic_rows(self, products, disabled_entities, template, request):
        historic = self._historic_port.get_by_filters(
            HistoricQueryRequest(
                excluded_entities=disabled_entities,
                product_types=products,
            )
        )
        data = historic.entries
        params = TemplatedDataProcessorParams(
            template=template,
            number_format=request.number_format,
            feature=Feature.HISTORIC,
            products=products,
            datetime_format=request.datetime_format,
            date_format=request.date_format,
        )
        return self._template_processor.process(data, params)

    def _resolve_template(self, template_config) -> Optional[object]:
        if not template_config:
            return None
        try:
            return self._template_port.get_by_id(UUID(template_config.id))
        except Exception as e:
            raise ExportException(f"Invalid template: {e}")
