import logging
from asyncio import Lock
from datetime import datetime
from uuid import UUID, uuid4

from application.ports.entity_port import EntityPort
from application.ports.file_rw_port import TableRWPort
from application.ports.position_port import PositionPort
from application.ports.template_parser_port import TemplateParserPort
from application.ports.template_port import TemplatePort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_port import TransactionPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from dateutil.tz import tzlocal
from domain.entity import Entity, Feature
from domain.exception.exceptions import ExecutionConflict, UnsupportedFileFormat
from domain.fetch_record import DataSource
from domain.importing import (
    ImportCandidate,
    ImportedData,
    ImportError,
    ImportErrorType,
    ImportFileRequest,
    ImportResult,
    ImportResultCode,
    TemplatedDataParserParams,
)
from domain.use_cases.import_file import ImportFile
from domain.virtual_data import VirtualDataImport, VirtualDataSource


class ImportFileImpl(ImportFile):
    def __init__(
        self,
        position_port: PositionPort,
        transaction_port: TransactionPort,
        table_rw_port: TableRWPort,
        entity_port: EntityPort,
        virtual_import_registry: VirtualImportRegistry,
        template_port: TemplatePort,
        template_parser: TemplateParserPort,
        transaction_handler_port: TransactionHandlerPort,
    ):
        self._position_port = position_port
        self._transaction_port = transaction_port
        self._table_rw_port = table_rw_port
        self._entity_port = entity_port
        self._virtual_import_registry = virtual_import_registry
        self._template_port = template_port
        self._template_parser = template_parser
        self._transaction_handler_port = transaction_handler_port
        self._lock = Lock()
        self._log = logging.getLogger(__name__)

    async def execute(self, request: ImportFileRequest) -> ImportResult:
        if self._lock.locked():
            raise ExecutionConflict()

        async with self._lock:
            template_cfg = request.template
            if not template_cfg or not template_cfg.id:
                return ImportResult(ImportResultCode.INVALID_TEMPLATE)

            template = self._template_port.get_by_id(UUID(template_cfg.id))
            if not template:
                return ImportResult(
                    ImportResultCode.INVALID_TEMPLATE,
                )

            parser_params = TemplatedDataParserParams(
                template=template,
                number_format=request.number_format,
                feature=request.feature,
                product=request.product,
                datetime_format=request.datetime_format,
                date_format=request.date_format,
                params=template_cfg.params or {},
            )

            if parser_params.feature != template.feature:
                return ImportResult(ImportResultCode.INVALID_TEMPLATE)

            try:
                table = self._table_rw_port.parse(request.file)
            except UnsupportedFileFormat as exc:
                self._log.warning("Unsupported file provided: %s", exc)
                return ImportResult(ImportResultCode.UNSUPPORTED_FILE_FORMAT)

            candidate = ImportCandidate(
                name=request.file.filename,
                source=DataSource.MANUAL,
                params=parser_params,
                data=table,
            )

            existing_entities = self._entity_port.get_all()
            existing_entities_by_name = {
                entity.name: entity for entity in existing_entities
            }

            async with self._transaction_handler_port.start():
                return await self._process_candidate(
                    request, candidate, existing_entities_by_name
                )

    async def _process_candidate(
        self,
        request: ImportFileRequest,
        candidate: ImportCandidate,
        existing_entities_by_name: dict[str, Entity],
    ) -> ImportResult:
        feature = request.feature
        preview = request.preview
        now = datetime.now(tzlocal())
        import_id = uuid4()
        virtual_entries: list[VirtualDataImport] = []
        errors: list[ImportError] = []
        positions = None
        transactions = None

        last_manual_imports = self._virtual_import_registry.get_last_import_records(
            source=VirtualDataSource.MANUAL
        )
        for entry in last_manual_imports:
            virtual_entries.append(
                VirtualDataImport(
                    import_id=import_id,
                    global_position_id=entry.global_position_id,
                    source=entry.source,
                    date=now,
                    feature=entry.feature,
                    entity_id=entry.entity_id,
                )
            )

        if feature == Feature.POSITION:
            result = self._template_parser.global_positions(
                [candidate], existing_entities_by_name
            )
            errors.extend(result.errors)
            positions = result.positions

            if not preview:
                for entity in result.created_entities:
                    self._entity_port.insert(entity)
                    existing_entities_by_name[entity.name] = entity

                for position in positions or []:
                    self._position_port.save(position)
                    virtual_entries.append(
                        VirtualDataImport(
                            import_id=import_id,
                            global_position_id=position.id,
                            source=VirtualDataSource.MANUAL,
                            date=now,
                            feature=Feature.POSITION,
                            entity_id=position.entity.id,
                        )
                    )

        elif feature == Feature.TRANSACTIONS:
            result = self._template_parser.transactions(
                [candidate], existing_entities_by_name
            )
            errors.extend(result.errors)
            transactions = result.transactions

            if not preview:
                for entity in result.created_entities:
                    self._entity_port.insert(entity)

                if transactions:
                    self._transaction_port.save(transactions)
                    tx_entities = {
                        tx.entity.id
                        for tx in (transactions.investment or [])
                        + (transactions.account or [])
                    }
                    for entity_id in tx_entities:
                        virtual_entries.append(
                            VirtualDataImport(
                                import_id=import_id,
                                global_position_id=None,
                                source=VirtualDataSource.MANUAL,
                                date=now,
                                feature=Feature.TRANSACTIONS,
                                entity_id=entity_id,
                            )
                        )
        else:
            return ImportResult(
                ImportResultCode.DISABLED,
                errors=[
                    ImportError(
                        type=ImportErrorType.UNEXPECTED_ERROR,
                        entry=request.file.filename,
                        detail=[f"Unsupported feature: {feature.value}"],
                    )
                ],
            )

        if virtual_entries and not preview:
            self._virtual_import_registry.insert(virtual_entries)

        imported_data = ImportedData(positions=positions, transactions=transactions)
        return ImportResult(
            ImportResultCode.COMPLETED,
            data=imported_data,
            errors=errors or None,
        )
