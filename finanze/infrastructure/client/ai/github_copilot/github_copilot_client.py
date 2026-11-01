import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Awaitable, Callable, Optional

from application.ports.ai_client import AIClient
from application.ports.device_connectable_integration import (
    DeviceConnectableIntegration,
)
from domain.ai import (
    AIClientFeature,
    AIGeneration,
    AIGenerationRequest,
    AIGenerationStatus,
    AIModel,
    AIModelCapability,
    AIReasoningEffort,
)
from domain.exception.exceptions import (
    AIProviderError,
    AIProviderErrorCode,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
)
from domain.external_integration import (
    DeviceAuthorizationPollResult,
    ExternalIntegrationDeviceAuthorization,
    ExternalIntegrationPayload,
)

from infrastructure.agent_runtime.runtime_pool import AgentRuntimePool
from infrastructure.agent_runtime.runtime_sandbox import (
    AgentRuntimeInstanceDirs,
    AgentRuntimeSandbox,
)
from infrastructure.client.ai.github_copilot.copilot_runtime_provisioner import (
    CopilotRuntimeProvisioner,
    CopilotRuntimeUnavailable,
)
from infrastructure.client.ai.github_copilot.copilot_runtime_types import (
    CopilotErrorKind,
    CopilotModelEntry,
    CopilotRuntimeError,
    CopilotRuntimeHandle,
)
from infrastructure.client.ai.github_copilot.github_device_flow import (
    GitHubDeviceFlow,
)

# Public client ID of the Finanze GitHub OAuth App; device flow uses no client secret.
GITHUB_COPILOT_CLIENT_ID = "Ov23liccSTjDfKjDuH22"
GITHUB_COPILOT_CLIENT_ID_ENV = "FINANZE_GITHUB_COPILOT_CLIENT_ID"
GITHUB_DEVICE_SCOPE = "read:user"
PROVIDER = "github_copilot"
CATALOG_TTL_SECONDS = 120
GENERATION_TIMEOUT_SECONDS = 120
REASONING_EFFORT_ORDER = ("low", "medium", "high", "xhigh", "max")
REASONING_EFFORTS = {
    AIReasoningEffort.NONE: "low",
    AIReasoningEffort.LOW: "low",
    AIReasoningEffort.MEDIUM: "medium",
    AIReasoningEffort.HIGH: "high",
    AIReasoningEffort.EXTRA_HIGH: "xhigh",
}

RuntimeFactory = Callable[
    [str, str, AgentRuntimeInstanceDirs], Awaitable[CopilotRuntimeHandle]
]


def resolve_github_copilot_client_id() -> str:
    return (
        os.getenv(GITHUB_COPILOT_CLIENT_ID_ENV, "").strip() or GITHUB_COPILOT_CLIENT_ID
    )


async def _start_copilot_runtime(
    executable: str, token: str, dirs: AgentRuntimeInstanceDirs
) -> CopilotRuntimeHandle:
    # Deferred: importing the Copilot SDK adds about a second to startup.
    from infrastructure.client.ai.github_copilot.copilot_runtime import CopilotRuntime

    return await CopilotRuntime.start(executable, token, dirs)


def _reasoning_effort(
    entry: CopilotModelEntry, requested: Optional[AIReasoningEffort]
) -> Optional[str]:
    if not entry.reasoning_efforts:
        return None
    preferred = REASONING_EFFORTS.get(requested) if requested else None
    if preferred in entry.reasoning_efforts:
        return preferred
    return next(
        (
            effort
            for effort in REASONING_EFFORT_ORDER
            if effort in entry.reasoning_efforts
        ),
        None,
    )


def _to_model(entry: CopilotModelEntry) -> AIModel:
    capabilities = {AIModelCapability.STRUCTURED_OUTPUT}
    if entry.reasoning_efforts:
        capabilities.add(AIModelCapability.REASONING)
    return AIModel(
        id=entry.id,
        name=entry.name,
        capabilities=capabilities,
        pricing=entry.pricing,
    )


class GitHubCopilotClient(AIClient, DeviceConnectableIntegration):
    def __init__(
        self,
        device_flow: GitHubDeviceFlow,
        provisioner: CopilotRuntimeProvisioner,
        pool: AgentRuntimePool,
        sandbox: AgentRuntimeSandbox,
        runtime_factory: RuntimeFactory = _start_copilot_runtime,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._device_flow = device_flow
        self._provisioner = provisioner
        self._pool = pool
        self._sandbox = sandbox
        self._runtime_factory = runtime_factory
        self._clock = clock
        self._catalogs: dict[str, tuple[float, list[CopilotModelEntry]]] = {}
        self._catalog_lock = asyncio.Lock()
        self._log = logging.getLogger(__name__)

    def features(self) -> set[AIClientFeature]:
        return {AIClientFeature.GENERATION, AIClientFeature.MODEL_LISTING}

    async def start_device_authorization(
        self, payload: ExternalIntegrationPayload
    ) -> ExternalIntegrationDeviceAuthorization:
        self._provisioner.prefetch()
        return await self._device_flow.start()

    async def poll_device_authorization(
        self, flow_id: str
    ) -> DeviceAuthorizationPollResult:
        return await self._device_flow.poll(flow_id)

    async def setup(self, payload: ExternalIntegrationPayload):
        token = payload.get("access_token")
        if not token:
            raise IntegrationSetupError(IntegrationSetupErrorCode.INVALID_CREDENTIALS)

        try:
            async with self._runtime(token) as runtime:
                if not await runtime.is_authenticated():
                    raise IntegrationSetupError(
                        IntegrationSetupErrorCode.INVALID_CREDENTIALS
                    )
                entries = await runtime.list_models()
        except CopilotRuntimeUnavailable as e:
            self._log.warning(f"GitHub Copilot runtime unavailable: {e}")
            raise IntegrationSetupError(IntegrationSetupErrorCode.RUNTIME_FAILED) from e
        except IntegrationSetupError:
            await self._pool.discard(PROVIDER, token)
            raise
        except CopilotRuntimeError as e:
            await self._pool.discard(PROVIDER, token)
            raise IntegrationSetupError(_setup_error_code(e.kind)) from e

        if not any(entry.enabled for entry in entries):
            await self._pool.discard(PROVIDER, token)
            raise IntegrationSetupError(IntegrationSetupErrorCode.NOT_ENTITLED)

        self._catalogs = {self._pool.fingerprint(token): (self._clock(), entries)}

    async def teardown(self):
        self._catalogs.clear()
        await self._pool.invalidate(PROVIDER)

    async def list_models(
        self, credentials: Optional[ExternalIntegrationPayload]
    ) -> list[AIModel]:
        entries = await self._catalog(self._token(credentials), max_age=0)
        return [_to_model(entry) for entry in entries if entry.enabled]

    async def get_model(
        self, model_id: str, credentials: Optional[ExternalIntegrationPayload]
    ) -> Optional[AIModel]:
        entry = await self._find(self._token(credentials), model_id)
        return _to_model(entry) if entry else None

    async def generate(
        self, request: AIGenerationRequest, credentials: ExternalIntegrationPayload
    ) -> AIGeneration:
        token = self._token(credentials)
        entry = await self._find(token, request.model)
        if entry is None:
            raise AIProviderError(
                AIProviderErrorCode.MODEL_NOT_FOUND,
                f"Model {request.model} is not available in GitHub Copilot",
            )

        try:
            async with self._runtime(token) as runtime:
                text = await runtime.complete(
                    model=entry.id,
                    instructions=request.instructions,
                    prompt="\n\n".join(message.content for message in request.messages),
                    schema=request.response_schema.schema
                    if request.response_schema
                    else None,
                    reasoning_effort=_reasoning_effort(entry, request.reasoning_effort),
                    timeout=GENERATION_TIMEOUT_SECONDS,
                )
        except CopilotRuntimeUnavailable as e:
            raise AIProviderError(
                AIProviderErrorCode.UNAVAILABLE,
                "GitHub Copilot runtime is not available",
            ) from e
        except CopilotRuntimeError as e:
            raise await self._provider_error(token, e) from e

        if not text:
            return AIGeneration(status=AIGenerationStatus.INCOMPLETE)
        return AIGeneration(status=AIGenerationStatus.COMPLETED, text=text)

    @asynccontextmanager
    async def _runtime(self, token: str) -> AsyncIterator[CopilotRuntimeHandle]:
        async with self._pool.use(
            PROVIDER, token, lambda: self._start_runtime(token)
        ) as runtime:
            yield runtime

    async def _start_runtime(self, token: str) -> CopilotRuntimeHandle:
        executable = await self._provisioner.ensure()
        dirs = await self._sandbox.create_instance(PROVIDER)
        try:
            return await self._runtime_factory(executable, token, dirs)
        except BaseException:
            await dirs.remove()
            raise

    async def _find(self, token: str, model_id: str) -> Optional[CopilotModelEntry]:
        entries = await self._catalog(token, max_age=CATALOG_TTL_SECONDS)
        return next(
            (entry for entry in entries if entry.id == model_id and entry.enabled),
            None,
        )

    async def _catalog(self, token: str, max_age: float) -> list[CopilotModelEntry]:
        key = self._pool.fingerprint(token)
        async with self._catalog_lock:
            cached = self._catalogs.get(key)
            if cached is not None and self._clock() - cached[0] < max_age:
                return cached[1]
            try:
                async with self._runtime(token) as runtime:
                    entries = await runtime.list_models()
            except CopilotRuntimeUnavailable as e:
                raise AIProviderError(
                    AIProviderErrorCode.UNAVAILABLE,
                    "GitHub Copilot runtime is not available",
                ) from e
            except CopilotRuntimeError as e:
                raise await self._provider_error(token, e) from e
            self._catalogs[key] = (self._clock(), entries)
            return entries

    async def _provider_error(
        self, token: str, error: CopilotRuntimeError
    ) -> AIProviderError:
        kind = error.kind
        if kind in (CopilotErrorKind.AUTH, CopilotErrorKind.FORBIDDEN):
            self._catalogs.pop(self._pool.fingerprint(token), None)
            await self._pool.discard(PROVIDER, token)
            return AIProviderError(
                AIProviderErrorCode.INVALID_CREDENTIALS,
                "GitHub Copilot rejected the connected account",
            )
        if kind == CopilotErrorKind.QUOTA:
            return AIProviderError(
                AIProviderErrorCode.INSUFFICIENT_FUNDS,
                "GitHub Copilot usage limit reached",
            )
        if kind == CopilotErrorKind.MODEL:
            self._catalogs.pop(self._pool.fingerprint(token), None)
            return AIProviderError(
                AIProviderErrorCode.MODEL_NOT_FOUND,
                "The selected model is no longer available in GitHub Copilot",
            )
        if kind == CopilotErrorKind.SCHEMA:
            return AIProviderError(
                AIProviderErrorCode.UNSUPPORTED_OPERATION,
                "The selected model does not support structured output",
            )
        if kind == CopilotErrorKind.RUNTIME:
            await self._pool.discard(PROVIDER, token)
        return AIProviderError(AIProviderErrorCode.UNAVAILABLE, str(error))

    @staticmethod
    def _token(credentials: Optional[ExternalIntegrationPayload]) -> str:
        token = (credentials or {}).get("access_token")
        if not token:
            raise AIProviderError(
                AIProviderErrorCode.INVALID_CREDENTIALS,
                "GitHub Copilot is not connected",
            )
        return token


def _setup_error_code(kind: CopilotErrorKind) -> IntegrationSetupErrorCode:
    if kind == CopilotErrorKind.AUTH:
        return IntegrationSetupErrorCode.INVALID_CREDENTIALS
    if kind == CopilotErrorKind.FORBIDDEN:
        return IntegrationSetupErrorCode.NOT_ENTITLED
    if kind == CopilotErrorKind.RUNTIME:
        return IntegrationSetupErrorCode.RUNTIME_FAILED
    return IntegrationSetupErrorCode.UNREACHABLE
