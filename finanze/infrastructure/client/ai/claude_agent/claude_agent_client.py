import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable, Optional

from application.ports.ai_client import AIClient
from domain.ai import (
    AIClientFeature,
    AIGeneration,
    AIGenerationRequest,
    AIGenerationStatus,
    AIInputModality,
    AIModel,
    AIModelCapability,
    AIUsage,
)
from domain.exception.exceptions import (
    AIProviderError,
    AIProviderErrorCode,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
)
from domain.external_integration import ExternalIntegrationPayload

from infrastructure.agent_runtime.runtime_pool import AgentRuntimePool
from infrastructure.agent_runtime.runtime_sandbox import (
    AgentRuntimeInstanceDirs,
    AgentRuntimeSandbox,
)
from infrastructure.client.ai.attachments import encode_attachment, is_image
from infrastructure.client.ai.claude_agent.claude_agent_types import (
    ClaudeAgentError,
    ClaudeCompletion,
    ClaudeErrorKind,
    ClaudeModelEntry,
    ClaudeOutcome,
    ClaudeRuntimeHandle,
)
from infrastructure.client.ai.claude_agent.claude_cli_locator import (
    ClaudeCli,
    ClaudeCliLocator,
    ClaudeCliNotFound,
    ClaudeCliOutdated,
)
from infrastructure.client.ai.claude_agent.claude_cli_runtime import ClaudeCliRuntime
from infrastructure.client.ai.claude_agent.claude_model_discovery import (
    ClaudeModelDiscovery,
)
from infrastructure.client.ai.reasoning_levels import pick_reasoning_level

PROVIDER = "claude_agent"
APPLICATION_NAME = "finanze"
CATALOG_TTL_SECONDS = 600
GENERATION_TIMEOUT_SECONDS = 180
FALLBACK_EFFORT_LEVELS = ("low", "medium", "high")
FALLBACK_MODELS = (
    ClaudeModelEntry("haiku", "Claude Haiku (latest)", FALLBACK_EFFORT_LEVELS),
    ClaudeModelEntry("sonnet", "Claude Sonnet (latest)", FALLBACK_EFFORT_LEVELS),
    ClaudeModelEntry("opus", "Claude Opus (latest)", FALLBACK_EFFORT_LEVELS),
)
FALLBACK_MODEL_IDS = {entry.id for entry in FALLBACK_MODELS}
CLAUDE_MODEL_PREFIX = "claude-"

RuntimeFactory = Callable[[str, AgentRuntimeInstanceDirs], ClaudeRuntimeHandle]


@dataclass(frozen=True)
class _Catalog:
    fetched_at: float
    entries: list[ClaudeModelEntry]
    discovered: bool


def _to_model(entry: ClaudeModelEntry) -> AIModel:
    capabilities = {AIModelCapability.STRUCTURED_OUTPUT}
    if entry.effort_levels:
        capabilities.add(AIModelCapability.REASONING)
    return AIModel(
        id=entry.id,
        name=entry.name,
        capabilities=capabilities,
        input_modalities={AIInputModality.TEXT, AIInputModality.IMAGE},
    )


def _to_generation(completion: ClaudeCompletion) -> AIGeneration:
    usage = (
        AIUsage(
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
        )
        if completion.input_tokens is not None and completion.output_tokens is not None
        else None
    )
    if completion.outcome == ClaudeOutcome.COMPLETED and completion.text:
        return AIGeneration(
            status=AIGenerationStatus.COMPLETED, text=completion.text, usage=usage
        )
    if completion.outcome == ClaudeOutcome.REFUSED:
        return AIGeneration(
            status=AIGenerationStatus.REFUSED, refusal=completion.text, usage=usage
        )
    return AIGeneration(status=AIGenerationStatus.INCOMPLETE, usage=usage)


def _accepts_unlisted(model_id: str) -> bool:
    return model_id in FALLBACK_MODEL_IDS or model_id.startswith(CLAUDE_MODEL_PREFIX)


class ClaudeAgentClient(AIClient):
    def __init__(
        self,
        locator: ClaudeCliLocator,
        discovery: ClaudeModelDiscovery,
        pool: AgentRuntimePool,
        sandbox: AgentRuntimeSandbox,
        client_app: str = APPLICATION_NAME,
        runtime_factory: Optional[RuntimeFactory] = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._locator = locator
        self._discovery = discovery
        self._pool = pool
        self._sandbox = sandbox
        self._runtime_factory = runtime_factory or (
            lambda executable, dirs: ClaudeCliRuntime(executable, dirs, client_app)
        )
        self._clock = clock
        self._catalogs: dict[str, _Catalog] = {}
        self._catalog_lock = asyncio.Lock()
        self._log = logging.getLogger(__name__)

    def features(self) -> set[AIClientFeature]:
        return {
            AIClientFeature.GENERATION,
            AIClientFeature.MODEL_LISTING,
            AIClientFeature.ATTACHMENTS,
        }

    async def setup(self, payload: ExternalIntegrationPayload):
        try:
            cli = await self._locator.locate(payload.get("cli_path"))
            signed_in = await self._locator.signed_in(cli)
        except ClaudeCliNotFound as e:
            raise IntegrationSetupError(
                IntegrationSetupErrorCode.RUNTIME_NOT_FOUND
            ) from e
        except ClaudeCliOutdated as e:
            raise IntegrationSetupError(
                IntegrationSetupErrorCode.RUNTIME_OUTDATED
            ) from e
        except ClaudeAgentError as e:
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNREACHABLE) from e
        if not signed_in:
            raise IntegrationSetupError(
                IntegrationSetupErrorCode.RUNTIME_NOT_AUTHENTICATED
            )

        self._catalogs.clear()
        await self._catalog(cli, max_age=0)

    async def teardown(self, payload: Optional[ExternalIntegrationPayload] = None):
        self._catalogs.clear()
        self._locator.invalidate()
        await self._pool.invalidate(PROVIDER)

    async def list_models(
        self, credentials: Optional[ExternalIntegrationPayload]
    ) -> list[AIModel]:
        catalog = await self._catalog(await self._cli(credentials), max_age=0)
        return [_to_model(entry) for entry in catalog.entries]

    async def get_model(
        self, model_id: str, credentials: Optional[ExternalIntegrationPayload]
    ) -> Optional[AIModel]:
        entry = await self._find(await self._cli(credentials), model_id)
        return _to_model(entry) if entry else None

    async def generate(
        self, request: AIGenerationRequest, credentials: ExternalIntegrationPayload
    ) -> AIGeneration:
        cli = await self._cli(credentials)
        entry = await self._find(cli, request.model)
        if entry is None:
            raise AIProviderError(
                AIProviderErrorCode.MODEL_NOT_FOUND,
                f"Model {request.model} is not available in Claude Agent",
            )

        attachments = [
            {
                "type": "image" if is_image(attachment) else "document",
                "source": {
                    "type": "base64",
                    "media_type": attachment.mime_type,
                    "data": encode_attachment(attachment),
                },
            }
            for message in request.messages
            for attachment in message.attachments
        ]
        try:
            async with self._pool.use(
                PROVIDER,
                cli.executable,
                lambda: self._start_runtime(cli.executable),
            ) as runtime:
                completion = await runtime.complete(
                    model=entry.id,
                    instructions=request.instructions,
                    prompt="\n\n".join(message.content for message in request.messages),
                    schema=request.response_schema.schema
                    if request.response_schema
                    else None,
                    effort=pick_reasoning_level(
                        entry.effort_levels, request.reasoning_effort
                    ),
                    timeout=GENERATION_TIMEOUT_SECONDS,
                    **({"attachments": attachments} if attachments else {}),
                )
        except ClaudeAgentError as e:
            raise await self._provider_error(cli, e) from e

        return _to_generation(completion)

    async def _start_runtime(self, executable: str) -> ClaudeRuntimeHandle:
        dirs = await self._sandbox.create_instance(PROVIDER)
        try:
            return self._runtime_factory(executable, dirs)
        except BaseException:
            await dirs.remove()
            raise

    async def _cli(
        self, credentials: Optional[ExternalIntegrationPayload]
    ) -> ClaudeCli:
        if credentials is None:
            raise AIProviderError(
                AIProviderErrorCode.INVALID_CREDENTIALS,
                "Claude Agent is not connected",
            )
        try:
            return await self._locator.locate(credentials.get("cli_path"))
        except ClaudeCliNotFound as e:
            raise AIProviderError(
                AIProviderErrorCode.UNAVAILABLE,
                "Claude Code was not found on this computer",
            ) from e
        except ClaudeCliOutdated as e:
            raise AIProviderError(
                AIProviderErrorCode.UNAVAILABLE,
                f"Claude Code {e.version} is too old, update it to continue",
            ) from e

    async def _find(self, cli: ClaudeCli, model_id: str) -> Optional[ClaudeModelEntry]:
        catalog = await self._catalog(cli, max_age=CATALOG_TTL_SECONDS)
        entry = next((entry for entry in catalog.entries if entry.id == model_id), None)
        if entry is None and not catalog.discovered and _accepts_unlisted(model_id):
            return ClaudeModelEntry(model_id, model_id, FALLBACK_EFFORT_LEVELS)
        return entry

    async def _catalog(self, cli: ClaudeCli, max_age: float) -> _Catalog:
        async with self._catalog_lock:
            cached = self._catalogs.get(cli.executable)
            if cached is not None and self._clock() - cached.fetched_at < max_age:
                return cached
            catalog = await self._discover(cli)
            self._catalogs[cli.executable] = catalog
            return catalog

    async def _discover(self, cli: ClaudeCli) -> _Catalog:
        dirs = await self._sandbox.create_instance(PROVIDER)
        try:
            entries = await self._discovery.discover(cli.executable, dirs.work)
        except ClaudeAgentError as e:
            self._log.warning(f"Could not list Claude Code models, using aliases: {e}")
            entries = []
        finally:
            await dirs.remove()
        if entries:
            return _Catalog(self._clock(), entries, discovered=True)
        return _Catalog(self._clock(), list(FALLBACK_MODELS), discovered=False)

    async def _provider_error(
        self, cli: ClaudeCli, error: ClaudeAgentError
    ) -> AIProviderError:
        kind = error.kind
        if kind == ClaudeErrorKind.AUTH:
            await self._pool.invalidate(PROVIDER)
            return AIProviderError(
                AIProviderErrorCode.INVALID_CREDENTIALS,
                "Claude Code is not signed in, sign in to it on this computer",
            )
        if kind == ClaudeErrorKind.BILLING:
            return AIProviderError(
                AIProviderErrorCode.INSUFFICIENT_FUNDS,
                "Claude usage credits or spend limit reached",
            )
        if kind == ClaudeErrorKind.MODEL:
            self._catalogs.pop(cli.executable, None)
            return AIProviderError(
                AIProviderErrorCode.MODEL_NOT_FOUND,
                "The selected Claude model is no longer available",
            )
        if kind == ClaudeErrorKind.CLI_OUTDATED:
            self._locator.invalidate()
            return AIProviderError(
                AIProviderErrorCode.UNAVAILABLE,
                "Update Claude Code to use the selected model",
            )
        if kind == ClaudeErrorKind.RUNTIME:
            await self._pool.invalidate(PROVIDER)
        return AIProviderError(AIProviderErrorCode.UNAVAILABLE, str(error))
