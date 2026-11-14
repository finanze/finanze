import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from application.ports.ai_client import AIClient
from application.ports.ai_import_extractor import AIImportExtractor
from application.ports.config_port import ConfigPort
from application.ports.external_integration_port import ExternalIntegrationPort
from domain.ai import (
    AIClientFeature,
    AIGenerationRequest,
    AIGenerationStatus,
    AIInputModality,
    AIJsonSchema,
    AIMessage,
    AIMessageRole,
    AIModel,
    AIModelCapability,
)
from domain.dezimal import Dezimal
from domain.exception.exceptions import AIProviderError, TooManyRequests
from domain.external_integration import (
    ExternalIntegrationId,
    ExternalIntegrationPayload,
)
from domain.importing import (
    AIImportExtraction,
    AIImportFailed,
    AIImportMetadata,
    AIImportRequest,
    ImportResultCode,
)
from domain.settings import AIProviderEntry, SettingsSection, effective_ai_providers
from infrastructure.ai_import.import_document import (
    DocumentSegment,
    ImportDocument,
    ImportDocumentReader,
)
from infrastructure.ai_import.import_schema import (
    REF_FIELD,
    SCHEMA_NAME,
    build_instructions,
    build_schema,
    import_schema_fields,
)

MAX_ROWS = 2000
MAX_OUTPUT_TOKENS = 16_000
SEGMENT_PROMPT = "Extract the rows from this part ({index}/{total}) of the document."
DOCUMENT_PROMPT = "Extract the rows from the attached document."
_NON_ALNUM = re.compile(r"[^0-9a-z]+")


@dataclass
class _Candidate:
    entry: AIProviderEntry
    client: AIClient
    credentials: ExternalIntegrationPayload
    model: Optional[AIModel]


def _normalized_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "").casefold()
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _NON_ALNUM.sub("", plain)


def _normalized_amount(value: str) -> str:
    try:
        return str(Dezimal(value).normalize())
    except Exception:
        return (value or "").strip()


def _fill_refs(fields: list[str], rows: list[list[str]]):
    if REF_FIELD not in fields:
        return
    index = {name: i for i, name in enumerate(fields)}
    ref_i = index[REF_FIELD]
    seen: dict[str, int] = {}
    for row in rows:
        if row[ref_i]:
            continue
        parts = [
            row[index["date"]][:10] if "date" in index else "",
            _normalized_amount(row[index["amount"]]) if "amount" in index else "",
            row[index["currency"]].upper() if "currency" in index else "",
            _normalized_name(row[index["name"]]) if "name" in index else "",
        ]
        digest = hashlib.sha256("|".join(parts).encode()).hexdigest()[:24]
        occurrence = seen.get(digest, 0)
        seen[digest] = occurrence + 1
        row[ref_i] = f"ai-{digest}" if occurrence == 0 else f"ai-{digest}-{occurrence}"


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def _parse_rows(text: Optional[str], fields: list[str]) -> list[list[str]]:
    if not text:
        raise ValueError("Empty response")
    body = json.loads(text)
    rows = body.get("rows") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Missing rows")
    parsed = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cells = [_cell(row.get(name)) for name in fields]
        if any(cells):
            parsed.append(cells)
    return parsed


class _CandidateFailed(Exception):
    pass


class AIImportExtractorAdapter(AIImportExtractor):
    def __init__(
        self,
        config_port: ConfigPort,
        external_integration_port: ExternalIntegrationPort,
        clients: dict[ExternalIntegrationId, AIClient],
        document_reader: ImportDocumentReader,
    ):
        self._config_port = config_port
        self._external_integration_port = external_integration_port
        self._clients = clients
        self._document_reader = document_reader
        self._no_vision: set[tuple[str, str]] = set()
        self._log = logging.getLogger(__name__)

    async def extract(self, request: AIImportRequest) -> AIImportExtraction:
        document = await self._document_reader.read(request.file)
        settings = await self._config_port.load_sections(
            {SettingsSection.AI, SettingsSection.IMPORTING}
        )
        import_config = settings.importing.ai if settings.importing else None
        entries = effective_ai_providers(
            settings.ai.providers if settings.ai else [],
            import_config.providers if import_config else [],
        )
        candidates = await self._candidates(entries, document.modality)
        if not candidates:
            code = (
                ImportResultCode.AI_VISION_UNSUPPORTED
                if document.modality is not None
                and await self._candidates(entries, None)
                else ImportResultCode.AI_UNAVAILABLE
            )
            raise AIImportFailed(code)

        schema_fields = import_schema_fields(request.fields)
        field_names = [field.field for field in schema_fields]
        user_instructions = "\n".join(
            part.strip()
            for part in (
                import_config.instructions if import_config else None,
                request.instructions,
            )
            if part and part.strip()
        )
        instructions = build_instructions(
            request.feature, request.product, schema_fields, user_instructions
        )
        schema = AIJsonSchema(
            name=SCHEMA_NAME, schema=build_schema(schema_fields, request.product)
        )

        last_error: Optional[str] = None
        for candidate in candidates:
            try:
                rows, requests = await self._run(
                    candidate, document, instructions, schema, field_names
                )
            except _CandidateFailed as e:
                last_error = str(e)
                self._log.warning(
                    "AI import with %s:%s failed (%s), trying the next priority",
                    candidate.entry.provider,
                    candidate.entry.model,
                    last_error,
                )
                continue
            if not rows:
                raise AIImportFailed(ImportResultCode.AI_EXTRACTION_EMPTY)
            _fill_refs(field_names, rows)
            return AIImportExtraction(
                fields=field_names,
                rows=rows,
                metadata=AIImportMetadata(
                    provider=candidate.entry.provider,
                    model=candidate.entry.model,
                    rows=len(rows),
                    requests=requests,
                    pages=document.pages,
                    images=document.modality is not None,
                ),
            )

        raise AIImportFailed(ImportResultCode.AI_UNAVAILABLE, last_error)

    async def _run(
        self,
        candidate: _Candidate,
        document: ImportDocument,
        instructions: str,
        schema: AIJsonSchema,
        field_names: list[str],
    ) -> tuple[list[list[str]], int]:
        rows: list[list[str]] = []
        total = len(document.segments)
        temperature = (
            Dezimal(0)
            if candidate.model is not None
            and AIModelCapability.TEMPERATURE in candidate.model.capabilities
            else None
        )
        for index, segment in enumerate(document.segments, start=1):
            prompt = self._prompt(segment, index, total)
            request = AIGenerationRequest(
                model=candidate.entry.model,
                messages=[
                    AIMessage(
                        role=AIMessageRole.USER,
                        content=prompt,
                        attachments=segment.attachments,
                    )
                ],
                instructions=instructions,
                response_schema=schema,
                temperature=temperature,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                upstream_provider=candidate.entry.upstreamProvider or None,
            )
            try:
                generation = await candidate.client.generate(
                    request, candidate.credentials
                )
            except (AIProviderError, TooManyRequests) as e:
                if segment.attachments and (
                    candidate.model is None or candidate.model.input_modalities is None
                ):
                    self._no_vision.add(
                        (candidate.entry.provider, candidate.entry.model)
                    )
                code = getattr(e, "code", None)
                raise _CandidateFailed(
                    code.value if code is not None else type(e).__name__
                ) from e
            if generation.status != AIGenerationStatus.COMPLETED:
                raise _CandidateFailed(generation.status.value)
            try:
                rows += _parse_rows(generation.text, field_names)
            except ValueError as e:
                raise _CandidateFailed("INVALID_RESPONSE") from e
            if len(rows) >= MAX_ROWS:
                return rows[:MAX_ROWS], index
        return rows, total

    @staticmethod
    def _prompt(segment: DocumentSegment, index: int, total: int) -> str:
        header = (
            SEGMENT_PROMPT.format(index=index, total=total)
            if total > 1
            else DOCUMENT_PROMPT
        )
        if not segment.text:
            return header
        return f"{header}\n<document>\n{segment.text}\n</document>"

    async def _candidates(
        self, entries: list[AIProviderEntry], modality: Optional[AIInputModality]
    ) -> list[_Candidate]:
        supported, unknown = [], []
        for entry in entries:
            candidate = await self._candidate(entry, modality)
            if candidate is None:
                continue
            modalities = candidate.model.input_modalities if candidate.model else None
            if modality is None or modalities is not None:
                supported.append(candidate)
            else:
                unknown.append(candidate)
        return supported + unknown

    async def _candidate(
        self, entry: AIProviderEntry, modality: Optional[AIInputModality]
    ) -> Optional[_Candidate]:
        try:
            provider_id = ExternalIntegrationId(entry.provider)
        except ValueError:
            return None
        client = self._clients.get(provider_id)
        if client is None or AIClientFeature.GENERATION not in client.features():
            return None
        if modality is not None:
            if AIClientFeature.ATTACHMENTS not in client.features():
                return None
            if (entry.provider, entry.model) in self._no_vision:
                return None
        credentials = await self._external_integration_port.get_payload(provider_id)
        if credentials is None:
            return None
        try:
            model = await client.get_model(entry.model, credentials)
        except (AIProviderError, TooManyRequests):
            model = None
        if model is not None:
            if (
                model.capabilities
                and AIModelCapability.STRUCTURED_OUTPUT not in model.capabilities
            ):
                return None
            if (
                modality is not None
                and model.input_modalities is not None
                and modality not in model.input_modalities
            ):
                return None
        return _Candidate(entry, client, credentials, model)
