import json
from io import BytesIO
from typing import Optional
from unittest.mock import AsyncMock

import pytest
from application.ports.ai_client import AIClient
from application.ports.config_port import ConfigPort
from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.file_rw_port import TableRWPort
from application.ports.pdf_page_renderer import PdfPageRenderer
from domain.ai import (
    AIAttachment,
    AIClientFeature,
    AIGeneration,
    AIGenerationStatus,
    AIInputModality,
    AIModel,
    AIModelCapability,
)
from domain.dezimal import Dezimal
from domain.entity import Feature
from domain.exception.exceptions import AIProviderError, AIProviderErrorCode
from domain.external_integration import ExternalIntegrationId
from domain.file_upload import FileUpload
from domain.global_position import ProductType
from domain.importing import AIImportFailed, AIImportRequest, ImportResultCode
from domain.settings import (
    AIConfig,
    AIImportConfig,
    AIProviderEntry,
    ImportConfig,
    PartialSettings,
)
from domain.template_fields import TEMPLATE_FIELD_MATRIX
from domain.template_type import TemplateType
from infrastructure.ai_import.ai_import_extractor_adapter import (
    AIImportExtractorAdapter,
)
from infrastructure.ai_import.import_document import ImportDocumentReader
from pypdf import PdfWriter

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
TEXT_FEATURES = {AIClientFeature.GENERATION}
VISION_FEATURES = {AIClientFeature.GENERATION, AIClientFeature.ATTACHMENTS}
ROW = {
    "ref": None,
    "name": "Coffee shop",
    "amount": "-3.50",
    "currency": "EUR",
    "type": None,
    "date": "2025-03-10",
}


def _account_fields():
    return [
        field
        for field in TEMPLATE_FIELD_MATRIX[Feature.TRANSACTIONS][ProductType.ACCOUNT]
        if field.template_type != TemplateType.EXPORT
    ]


def _row(**overrides):
    return {**ROW, **overrides}


class FakeClient(AIClient):
    def __init__(
        self,
        features=VISION_FEATURES,
        model: Optional[AIModel] = None,
        rows: Optional[list] = None,
        error: Optional[Exception] = None,
        status: AIGenerationStatus = AIGenerationStatus.COMPLETED,
    ):
        self._features = features
        self.model = model
        self.rows = rows if rows is not None else [_row()]
        self.error = error
        self.status = status
        self.requests = []

    async def setup(self, payload):
        pass

    def features(self):
        return self._features

    async def get_model(self, model_id, credentials):
        return self.model

    async def generate(self, request, credentials):
        self.requests.append(request)
        if self.error:
            raise self.error
        return AIGeneration(status=self.status, text=json.dumps({"rows": self.rows}))


def _settings(default, override=None, instructions=None):
    return PartialSettings(
        ai=AIConfig(providers=default),
        importing=ImportConfig(
            ai=AIImportConfig(providers=override or [], instructions=instructions)
        ),
    )


def _upload(name, data, content_type="application/octet-stream"):
    return FileUpload(
        filename=name,
        content_type=content_type,
        content_length=len(data),
        data=BytesIO(data),
    )


def _request(upload, instructions=None):
    return AIImportRequest(
        file=upload,
        feature=Feature.TRANSACTIONS,
        product=ProductType.ACCOUNT,
        fields=_account_fields(),
        instructions=instructions,
    )


def _adapter(settings, clients, table_rows=None, renderer=None):
    config = AsyncMock(spec=ConfigPort)
    config.load_sections.return_value = settings
    integrations = AsyncMock(spec=ExternalIntegrationPort)
    integrations.get_payload.return_value = {"api_key": "k"}
    table = AsyncMock(spec=TableRWPort)
    table.parse.return_value = table_rows or [
        ["Concept", "Amount"],
        ["Coffee", "-3,50"],
    ]
    return AIImportExtractorAdapter(
        config,
        integrations,
        clients,
        ImportDocumentReader(table, page_renderer=renderer),
    )


OPENAI = ExternalIntegrationId.OPENAI
OPENROUTER = ExternalIntegrationId.OPENROUTER


def _entry(provider=OPENAI, model="m"):
    return AIProviderEntry(provider=provider.value, model=model)


class TestTextExtraction:
    @pytest.mark.asyncio
    async def test_extracts_rows_with_canonical_fields_and_refs(self):
        client = FakeClient(features=TEXT_FEATURES, rows=[_row(), _row()])
        adapter = _adapter(_settings([_entry()]), {OPENAI: client})

        result = await adapter.extract(
            _request(_upload("statement.txt", b"10/03 Coffee shop -3,50"))
        )

        assert "entity" not in result.fields
        assert "amount_in" not in result.fields
        index = result.fields.index("ref")
        refs = [row[index] for row in result.rows]
        assert refs[0].startswith("ai-") and refs[1] == f"{refs[0]}-1"
        assert result.rows[0][result.fields.index("amount")] == "-3.50"
        assert result.metadata.provider == "OPENAI"
        assert result.metadata.rows == 2
        assert result.metadata.images is False
        request = client.requests[0]
        assert "Coffee shop" in request.messages[0].content
        assert request.messages[0].attachments == []
        assert request.response_schema.schema["properties"]["rows"]["type"] == "array"

    @pytest.mark.asyncio
    async def test_ref_is_stable_across_name_formatting(self):
        first = FakeClient(features=TEXT_FEATURES, rows=[_row(name="Café  Shop")])
        second = FakeClient(features=TEXT_FEATURES, rows=[_row(name="CAFE SHOP")])
        a = await _adapter(_settings([_entry()]), {OPENAI: first}).extract(
            _request(_upload("a.txt", b"x"))
        )
        b = await _adapter(_settings([_entry()]), {OPENAI: second}).extract(
            _request(_upload("b.txt", b"x"))
        )
        index = a.fields.index("ref")
        assert a.rows[0][index] == b.rows[0][index]

    @pytest.mark.asyncio
    async def test_keeps_printed_refs(self):
        client = FakeClient(features=TEXT_FEATURES, rows=[_row(ref="BANK-1")])
        result = await _adapter(_settings([_entry()]), {OPENAI: client}).extract(
            _request(_upload("a.txt", b"x"))
        )
        assert result.rows[0][result.fields.index("ref")] == "BANK-1"

    @pytest.mark.asyncio
    async def test_table_files_are_chunked_with_header(self):
        rows = [["Concept", "Amount"]] + [[f"Row {i}", "1"] for i in range(85)]
        client = FakeClient(features=TEXT_FEATURES)
        adapter = _adapter(_settings([_entry()]), {OPENAI: client}, table_rows=rows)

        result = await adapter.extract(_request(_upload("a.csv", b"x", "text/csv")))

        assert len(client.requests) == 3
        assert all(
            "Concept | Amount" in request.messages[0].content
            for request in client.requests
        )
        assert result.metadata.requests == 3

    @pytest.mark.asyncio
    async def test_instructions_merge_settings_and_request(self):
        client = FakeClient(features=TEXT_FEATURES)
        adapter = _adapter(
            _settings([_entry()], instructions="Saved note"), {OPENAI: client}
        )
        await adapter.extract(_request(_upload("a.txt", b"x"), "Ignore card fees"))
        instructions = client.requests[0].instructions
        assert "Saved note" in instructions
        assert "Ignore card fees" in instructions

    @pytest.mark.asyncio
    async def test_temperature_zero_only_with_capability(self):
        with_temp = FakeClient(
            features=TEXT_FEATURES,
            model=AIModel(
                id="m",
                name="m",
                capabilities={
                    AIModelCapability.STRUCTURED_OUTPUT,
                    AIModelCapability.TEMPERATURE,
                },
            ),
        )
        await _adapter(_settings([_entry()]), {OPENAI: with_temp}).extract(
            _request(_upload("a.txt", b"x"))
        )
        assert with_temp.requests[0].temperature == Dezimal(0)

        without = FakeClient(features=TEXT_FEATURES)
        await _adapter(_settings([_entry()]), {OPENAI: without}).extract(
            _request(_upload("a.txt", b"x"))
        )
        assert without.requests[0].temperature is None


class TestCandidates:
    @pytest.mark.asyncio
    async def test_import_override_replaces_shared_list(self):
        shared = FakeClient(features=TEXT_FEATURES)
        override = FakeClient(features=TEXT_FEATURES)
        adapter = _adapter(
            _settings([_entry(OPENAI)], [_entry(OPENROUTER)]),
            {OPENAI: shared, OPENROUTER: override},
        )
        result = await adapter.extract(_request(_upload("a.txt", b"x")))
        assert result.metadata.provider == "OPENROUTER"
        assert shared.requests == []

    @pytest.mark.asyncio
    async def test_falls_back_on_provider_error(self):
        failing = FakeClient(
            features=TEXT_FEATURES,
            error=AIProviderError(AIProviderErrorCode.INSUFFICIENT_FUNDS, "x"),
        )
        working = FakeClient(features=TEXT_FEATURES)
        adapter = _adapter(
            _settings([_entry(OPENAI), _entry(OPENROUTER)]),
            {OPENAI: failing, OPENROUTER: working},
        )
        result = await adapter.extract(_request(_upload("a.txt", b"x")))
        assert result.metadata.provider == "OPENROUTER"

    @pytest.mark.asyncio
    async def test_all_failing_raises_unavailable_with_detail(self):
        failing = FakeClient(features=TEXT_FEATURES, status=AIGenerationStatus.REFUSED)
        adapter = _adapter(_settings([_entry()]), {OPENAI: failing})
        with pytest.raises(AIImportFailed) as error:
            await adapter.extract(_request(_upload("a.txt", b"x")))
        assert error.value.code == ImportResultCode.AI_UNAVAILABLE
        assert error.value.detail == "REFUSED"

    @pytest.mark.asyncio
    async def test_no_providers_is_unavailable(self):
        adapter = _adapter(_settings([]), {})
        with pytest.raises(AIImportFailed) as error:
            await adapter.extract(_request(_upload("a.txt", b"x")))
        assert error.value.code == ImportResultCode.AI_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_skips_models_without_structured_output(self):
        client = FakeClient(
            features=TEXT_FEATURES,
            model=AIModel(id="m", name="m", capabilities={AIModelCapability.DECISIONS}),
        )
        adapter = _adapter(_settings([_entry()]), {OPENAI: client})
        with pytest.raises(AIImportFailed):
            await adapter.extract(_request(_upload("a.txt", b"x")))
        assert client.requests == []

    @pytest.mark.asyncio
    async def test_empty_rows_raise_extraction_empty(self):
        client = FakeClient(features=TEXT_FEATURES, rows=[])
        adapter = _adapter(_settings([_entry()]), {OPENAI: client})
        with pytest.raises(AIImportFailed) as error:
            await adapter.extract(_request(_upload("a.txt", b"x")))
        assert error.value.code == ImportResultCode.AI_EXTRACTION_EMPTY


def _vision_model(modalities):
    return AIModel(
        id="m",
        name="m",
        capabilities={AIModelCapability.STRUCTURED_OUTPUT},
        input_modalities=modalities,
    )


class TestImages:
    @pytest.mark.asyncio
    async def test_images_go_to_known_vision_models_first(self):
        unknown = FakeClient(model=None)
        vision = FakeClient(
            model=_vision_model({AIInputModality.TEXT, AIInputModality.IMAGE})
        )
        adapter = _adapter(
            _settings([_entry(OPENAI), _entry(OPENROUTER)]),
            {OPENAI: unknown, OPENROUTER: vision},
        )
        result = await adapter.extract(_request(_upload("receipt.png", PNG)))
        assert result.metadata.provider == "OPENROUTER"
        assert result.metadata.images is True
        attachment = vision.requests[0].messages[0].attachments[0]
        assert attachment.mime_type == "image/png"
        assert unknown.requests == []

    @pytest.mark.asyncio
    async def test_text_only_models_report_vision_unsupported(self):
        text_only = FakeClient(model=_vision_model({AIInputModality.TEXT}))
        no_attachments = FakeClient(features=TEXT_FEATURES)
        adapter = _adapter(
            _settings([_entry(OPENAI), _entry(OPENROUTER)]),
            {OPENAI: text_only, OPENROUTER: no_attachments},
        )
        with pytest.raises(AIImportFailed) as error:
            await adapter.extract(_request(_upload("receipt.png", PNG)))
        assert error.value.code == ImportResultCode.AI_VISION_UNSUPPORTED

    @pytest.mark.asyncio
    async def test_unknown_model_failing_with_image_is_not_retried(self):
        client = FakeClient(
            model=None, error=AIProviderError(AIProviderErrorCode.UNAVAILABLE, "400")
        )
        adapter = _adapter(_settings([_entry()]), {OPENAI: client})
        with pytest.raises(AIImportFailed):
            await adapter.extract(_request(_upload("receipt.png", PNG)))
        with pytest.raises(AIImportFailed) as error:
            await adapter.extract(_request(_upload("receipt.png", PNG)))
        assert error.value.code == ImportResultCode.AI_VISION_UNSUPPORTED
        assert len(client.requests) == 1

    @pytest.mark.asyncio
    async def test_scanned_pdf_pages_are_rendered(self):
        renderer = AsyncMock(spec=PdfPageRenderer)
        renderer.render.return_value = [
            AIAttachment(mime_type="image/jpeg", data=b"\xff\xd8\xff1"),
            AIAttachment(mime_type="image/jpeg", data=b"\xff\xd8\xff2"),
        ]
        client = FakeClient(model=_vision_model({AIInputModality.IMAGE}))
        adapter = _adapter(_settings([_entry()]), {OPENAI: client}, renderer=renderer)

        result = await adapter.extract(_request(_upload("scan.pdf", _blank_pdf())))

        assert len(client.requests) == 2
        assert result.metadata.pages == 2
        assert result.metadata.images is True

    @pytest.mark.asyncio
    async def test_scanned_pdf_without_renderer_is_sent_as_document(self):
        client = FakeClient(model=_vision_model({AIInputModality.DOCUMENT}))
        adapter = _adapter(_settings([_entry()]), {OPENAI: client})

        await adapter.extract(_request(_upload("scan.pdf", _blank_pdf())))

        attachment = client.requests[0].messages[0].attachments[0]
        assert attachment.mime_type == "application/pdf"


def _blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()
