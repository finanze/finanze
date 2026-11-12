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
from application.ports.transaction_labeler import TransactionLabeler
from application.ports.transaction_port import TransactionPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from dateutil.tz import tzlocal
from domain.entity import Entity, Feature
from domain.exception.exceptions import (
    ExecutionConflict,
    InvalidTemplateDefaultValue,
    NoTableFound,
    PdfNoTextLayer,
    UnsupportedFileFormat,
)
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.importing import (
    ImportCandidate,
    ImportedData,
    ImportError,
    ImportErrorType,
    ImportFileRequest,
    ImportResult,
    ImportResultCode,
    PositionImportResult,
    TemplatedDataParserParams,
    TransactionsImportResult,
    exclude_duplicated_txs,
    stored_entity_ids,
)
from domain.labeling import LabelingTrigger
from domain.settlement import settlement_window
from domain.template import (
    Template,
    TemplatedField,
    get_effective_field,
    missing_required_template_fields,
    validate_template_default_values,
)
from domain.template_fields import TEMPLATE_FIELD_MATRIX, TemplateField
from domain.template_type import TemplateType
from domain.transactions import AccountTxSelection
from domain.use_cases.import_file import ImportFile
from domain.virtual_data import VirtualDataImport, VirtualDataSource

IMPORTABLE_FEATURES = {Feature.POSITION, Feature.TRANSACTIONS}


def _importable_product_fields(
    feature: Feature, product: ProductType
) -> list[TemplateField] | None:
    if feature not in IMPORTABLE_FEATURES:
        return None
    product_fields = TEMPLATE_FIELD_MATRIX.get(feature, {}).get(product)
    if not product_fields:
        return None
    return [
        field for field in product_fields if field.template_type != TemplateType.EXPORT
    ]


def _validate_ephemeral_template(
    template: Template, importable_fields: list[TemplateField]
) -> bool:
    if not template.fields:
        return False
    allowed_names = {f.field for f in importable_fields}
    available_fields: set[str] = set()
    for tf in template.fields:
        if tf.field not in allowed_names:
            return False
        if get_effective_field(tf.field, tf.name, tf.default_value, template) is None:
            return False
        if (tf.name and tf.name.strip()) or tf.default_value is not None:
            available_fields.add(tf.field)
    try:
        validate_template_default_values(template)
    except InvalidTemplateDefaultValue:
        return False
    return (
        len(missing_required_template_fields(importable_fields, available_fields)) == 0
    )


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
        transaction_labeler: TransactionLabeler,
    ):
        self._position_port = position_port
        self._transaction_port = transaction_port
        self._table_rw_port = table_rw_port
        self._entity_port = entity_port
        self._virtual_import_registry = virtual_import_registry
        self._template_port = template_port
        self._template_parser = template_parser
        self._transaction_handler_port = transaction_handler_port
        self._transaction_labeler = transaction_labeler
        self._lock = Lock()
        self._log = logging.getLogger(__name__)

    async def _parse_table(self, request: ImportFileRequest):
        try:
            return await self._table_rw_port.parse(request.file), None
        except PdfNoTextLayer as exc:
            self._log.warning("PDF without selectable text provided: %s", exc)
            return None, ImportResult(ImportResultCode.PDF_NO_TEXT_LAYER)
        except NoTableFound as exc:
            self._log.warning("No table found in file: %s", exc)
            return None, ImportResult(ImportResultCode.NO_TABLE_FOUND)
        except UnsupportedFileFormat as exc:
            self._log.warning("Unsupported file provided: %s", exc)
            return None, ImportResult(ImportResultCode.UNSUPPORTED_FILE_FORMAT)

    async def _resolve_template_and_table(self, request: ImportFileRequest):
        template_cfg = request.template
        if template_cfg is not None:
            if not template_cfg.id:
                return None, None, None, ImportResult(ImportResultCode.INVALID_TEMPLATE)
            try:
                template_uuid = UUID(template_cfg.id)
            except ValueError:
                return None, None, None, ImportResult(ImportResultCode.INVALID_TEMPLATE)
            template = await self._template_port.get_by_id(template_uuid)
            if not template or template.feature != request.feature:
                return None, None, None, ImportResult(ImportResultCode.INVALID_TEMPLATE)
            table, err = await self._parse_table(request)
            if err is not None:
                return None, None, None, err
            params = template_cfg.params or request.template_params or {}
            return template, params, table, None

        importable_fields = _importable_product_fields(request.feature, request.product)
        if not importable_fields:
            return None, None, None, ImportResult(ImportResultCode.INVALID_TEMPLATE)

        if request.template_fields is not None:
            ephemeral = Template(
                id=None,
                name="",
                feature=request.feature,
                type=TemplateType.IMPORT,
                fields=request.template_fields,
                products=[request.product],
            )
            if not _validate_ephemeral_template(ephemeral, importable_fields):
                return None, None, None, ImportResult(ImportResultCode.INVALID_TEMPLATE)
            table, err = await self._parse_table(request)
            if err is not None:
                return None, None, None, err
            return ephemeral, request.template_params or {}, table, None

        table, err = await self._parse_table(request)
        if err is not None:
            return None, None, None, err
        suggestion = await self._template_parser.suggest_fields(
            table, importable_fields, []
        )
        auto_fields = [
            TemplatedField(field=f.field, name=f.name) for f in suggestion.fields
        ]
        if (
            "currency" in suggestion.missing_required_fields
            and suggestion.detected_currency
        ):
            auto_fields.append(
                TemplatedField(
                    field="currency",
                    name="currency",
                    default_value=suggestion.detected_currency,
                )
            )
        ephemeral = Template(
            id=None,
            name="",
            feature=request.feature,
            type=TemplateType.IMPORT,
            fields=auto_fields,
            products=[request.product],
        )
        if not _validate_ephemeral_template(ephemeral, importable_fields):
            return None, None, None, ImportResult(ImportResultCode.INVALID_TEMPLATE)
        return ephemeral, request.template_params or {}, table, None

    async def execute(self, request: ImportFileRequest) -> ImportResult:
        if self._lock.locked():
            raise ExecutionConflict()

        async with self._lock:
            template, params, table, err = await self._resolve_template_and_table(
                request
            )
            if err is not None:
                return err

            parser_params = TemplatedDataParserParams(
                template=template,
                number_format=request.number_format,
                feature=request.feature,
                product=request.product,
                datetime_format=request.datetime_format,
                date_format=request.date_format,
                params=params,
            )

            candidate = ImportCandidate(
                name=request.file.filename,
                source=DataSource.MANUAL,
                params=parser_params,
                data=table,
            )

            existing_entities = await self._entity_port.get_all()
            existing_entities_by_name = {
                entity.name: entity for entity in existing_entities
            }

            async with self._transaction_handler_port.start():
                result = await self._process_candidate(
                    request, candidate, existing_entities_by_name
                )

            imported_txs = result.data.transactions if result.data else None
            if not request.preview and imported_txs and imported_txs.account:
                await self._transaction_labeler.classify_external(
                    AccountTxSelection(ids=[tx.id for tx in imported_txs.account]),
                    LabelingTrigger.AUTO,
                )
            return result

    async def _finalize_positions(
        self,
        result: PositionImportResult,
        preview: bool,
        import_id: UUID,
        now: datetime,
        virtual_entries: list[VirtualDataImport],
        existing_entities_by_name: dict[str, Entity],
        errors: list[ImportError],
    ):
        errors.extend(result.errors)
        positions = result.positions
        if not preview:
            for entity in result.created_entities:
                await self._entity_port.insert(entity)
                existing_entities_by_name[entity.name] = entity

            for position in positions or []:
                await self._position_port.save(position)
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
        return positions

    async def _finalize_transactions(
        self,
        result: TransactionsImportResult,
        preview: bool,
        import_id: UUID,
        now: datetime,
        virtual_entries: list[VirtualDataImport],
        errors: list[ImportError],
    ):
        errors.extend(result.errors)
        existing_keys = await self._transaction_port.get_ref_keys(
            stored_entity_ids(result)
        )
        transactions, duplicated = exclude_duplicated_txs(result, existing_keys)
        errors.extend(duplicated)

        if not preview:
            for entity in result.created_entities:
                await self._entity_port.insert(entity)

            if transactions:
                await self._transaction_port.save(transactions)
                if transactions.account:
                    await self._transaction_labeler.classify(
                        AccountTxSelection(ids=[tx.id for tx in transactions.account])
                    )
                if transactions.investment:
                    await self._transaction_labeler.link_settlements(
                        settlement_window(transactions.investment)
                    )
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
        return transactions

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

        last_manual_imports = (
            await self._virtual_import_registry.get_last_import_records(
                source=VirtualDataSource.MANUAL
            )
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
            pos_result = await self._template_parser.global_positions(
                [candidate], existing_entities_by_name
            )
            positions = await self._finalize_positions(
                pos_result,
                preview,
                import_id,
                now,
                virtual_entries,
                existing_entities_by_name,
                errors,
            )

        elif feature == Feature.TRANSACTIONS:
            tx_result = await self._template_parser.transactions(
                [candidate], existing_entities_by_name
            )
            transactions = await self._finalize_transactions(
                tx_result,
                preview,
                import_id,
                now,
                virtual_entries,
                errors,
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
            await self._virtual_import_registry.insert(virtual_entries)

        imported_data = ImportedData(positions=positions, transactions=transactions)
        return ImportResult(
            ImportResultCode.COMPLETED,
            data=imported_data,
            errors=errors or None,
        )
