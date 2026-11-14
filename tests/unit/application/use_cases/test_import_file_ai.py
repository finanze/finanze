from io import BytesIO
from unittest.mock import AsyncMock, MagicMock

import pytest
from application.ports.ai_import_extractor import AIImportExtractor
from application.ports.entity_port import EntityPort
from application.ports.file_rw_port import TableRWPort
from application.ports.position_port import PositionPort
from application.ports.template_port import TemplatePort
from application.ports.transaction_labeler import TransactionLabeler
from application.ports.transaction_port import TransactionPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from application.use_cases.import_file import ImportFileImpl
from domain.dezimal import Dezimal
from domain.entity import Feature
from domain.export import NumberFormat
from domain.file_upload import FileUpload
from domain.global_position import ProductType
from domain.importing import (
    AIImportExtraction,
    AIImportFailed,
    AIImportMetadata,
    ImportFileRequest,
    ImportResultCode,
)
from domain.transactions import TxType
from infrastructure.ai_import.memory_import_preview_store import (
    MemoryImportPreviewStore,
)
from infrastructure.templating.templated_data_parser import TemplateDataParser

FIELDS = ["ref", "name", "amount", "currency", "type", "date"]
ROWS = [
    ["ai-1", "Coffee shop", "-3.50", "EUR", "", "2025-03-10"],
    ["ai-2", "Salary", "1500", "EUR", "", "2025-03-01T09:30:00"],
]


def _extraction(rows=None):
    return AIImportExtraction(
        fields=FIELDS,
        rows=rows if rows is not None else [list(row) for row in ROWS],
        metadata=AIImportMetadata(provider="OPENAI", model="m", rows=2),
    )


def _request(preview=True, token=None, with_file=True):
    return ImportFileRequest(
        file=FileUpload(
            filename="statement.pdf",
            content_type="application/pdf",
            content_length=1,
            data=BytesIO(b"x"),
        )
        if with_file
        else None,
        number_format=NumberFormat.EUROPEAN,
        feature=Feature.TRANSACTIONS,
        product=ProductType.ACCOUNT,
        datetime_format="%d/%m/%Y",
        date_format=None,
        preview=preview,
        template_params={"entity": "My Bank"},
        use_ai=True,
        ai_instructions="note",
        preview_token=token,
    )


def _build(extractor_result=None, error=None, store=None):
    transaction_port = AsyncMock(spec=TransactionPort)
    transaction_port.get_ref_keys.return_value = set()
    entity_port = AsyncMock(spec=EntityPort)
    entity_port.get_all.return_value = []
    registry = AsyncMock(spec=VirtualImportRegistry)
    registry.get_last_import_records.return_value = []
    handler = MagicMock()
    handler.start.return_value = AsyncMock()
    extractor = AsyncMock(spec=AIImportExtractor)
    if error:
        extractor.extract.side_effect = error
    else:
        extractor.extract.return_value = extractor_result or _extraction()
    table_port = AsyncMock(spec=TableRWPort)
    use_case = ImportFileImpl(
        AsyncMock(spec=PositionPort),
        transaction_port,
        table_port,
        entity_port,
        registry,
        AsyncMock(spec=TemplatePort),
        TemplateDataParser(),
        handler,
        AsyncMock(spec=TransactionLabeler),
        ai_import_extractor=extractor,
        preview_store=store or MemoryImportPreviewStore(),
    )
    return use_case, extractor, transaction_port, table_port


class TestAIImport:
    @pytest.mark.asyncio
    async def test_preview_parses_canonical_rows_and_returns_token(self):
        use_case, extractor, transaction_port, table_port = _build()

        result = await use_case.execute(_request())

        assert result.code == ImportResultCode.COMPLETED
        txs = result.data.transactions.account
        assert [tx.name for tx in txs] == ["Coffee shop", "Salary"]
        assert txs[0].amount == Dezimal("3.50")
        assert txs[0].type == TxType.OUTFLOW
        assert txs[1].type == TxType.INFLOW
        assert txs[1].date.hour == 9
        assert txs[0].entity.name == "My Bank"
        assert result.preview_token
        assert result.ai.provider == "OPENAI"
        request = extractor.extract.call_args.args[0]
        assert request.instructions == "note"
        assert "entity" in {field.field for field in request.fields}
        table_port.parse.assert_not_called()
        transaction_port.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_confirm_with_token_reuses_extraction(self):
        use_case, extractor, transaction_port, _ = _build()
        preview = await use_case.execute(_request())

        result = await use_case.execute(
            _request(preview=False, token=preview.preview_token, with_file=False)
        )

        assert result.code == ImportResultCode.COMPLETED
        assert extractor.extract.call_count == 1
        transaction_port.save.assert_called_once()
        assert result.preview_token is None
        assert result.ai.model == "m"

    @pytest.mark.asyncio
    async def test_token_is_single_use(self):
        use_case, _, _, _ = _build()
        preview = await use_case.execute(_request())
        await use_case.execute(_request(preview=False, token=preview.preview_token))

        result = await use_case.execute(
            _request(preview=False, token=preview.preview_token)
        )

        assert result.code == ImportResultCode.PREVIEW_EXPIRED

    @pytest.mark.asyncio
    async def test_unknown_token_expired(self):
        use_case, extractor, _, _ = _build()
        result = await use_case.execute(
            _request(preview=False, token="missing", with_file=False)
        )
        assert result.code == ImportResultCode.PREVIEW_EXPIRED
        extractor.extract.assert_not_called()

    @pytest.mark.asyncio
    async def test_extractor_failure_maps_to_result(self):
        use_case, _, _, _ = _build(
            error=AIImportFailed(ImportResultCode.AI_VISION_UNSUPPORTED, "detail")
        )
        result = await use_case.execute(_request())
        assert result.code == ImportResultCode.AI_VISION_UNSUPPORTED
        assert result.detail == "detail"

    @pytest.mark.asyncio
    async def test_invalid_rows_are_reported_as_errors(self):
        rows = [list(ROWS[0]), ["ai-3", "Broken", "abc", "EUR", "", "2025-03-02"]]
        use_case, _, _, _ = _build(extractor_result=_extraction(rows))
        result = await use_case.execute(_request())
        assert result.code == ImportResultCode.COMPLETED
        assert len(result.data.transactions.account) == 1
        assert result.errors

    @pytest.mark.asyncio
    async def test_missing_file_without_token(self):
        use_case, extractor, _, _ = _build()
        result = await use_case.execute(_request(with_file=False))
        assert result.code == ImportResultCode.UNSUPPORTED_FILE_FORMAT
        extractor.extract.assert_not_called()

    @pytest.mark.asyncio
    async def test_without_extractor_is_unavailable(self):
        use_case = ImportFileImpl(
            *(AsyncMock() for _ in range(6)),
            TemplateDataParser(),
            MagicMock(),
            AsyncMock(),
        )
        result = await use_case.execute(_request())
        assert result.code == ImportResultCode.AI_UNAVAILABLE


class TestMemoryImportPreviewStore:
    def test_expires_and_caps_entries(self):
        now = [0.0]
        store = MemoryImportPreviewStore(clock=lambda: now[0])
        preview = MagicMock()
        tokens = [store.save(preview) for _ in range(9)]
        assert store.take(tokens[0]) is None
        assert store.take(tokens[1]) is preview
        now[0] = 31 * 60
        assert store.take(tokens[2]) is None

    def test_clear(self):
        store = MemoryImportPreviewStore()
        token = store.save(MagicMock())
        store.clear()
        assert store.take(token) is None
