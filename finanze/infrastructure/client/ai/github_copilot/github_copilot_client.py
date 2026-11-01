import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import AsyncIterator, Awaitable, Callable, Optional, TypeVar

from application.ports.ai_client import AIClient
from application.ports.device_connectable_integration import (
    DeviceConnectableIntegration,
)
from application.ports.external_integration_port import ExternalIntegrationPort
from dateutil.tz import tzlocal
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
    ExternalIntegrationId,
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
TOKEN_REFRESH_MARGIN = timedelta(minutes=5)
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
T = TypeVar("T")


def _local_now() -> datetime:
    return datetime.now(tzlocal())


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
        external_integration_port: ExternalIntegrationPort,
        runtime_factory: RuntimeFactory = _start_copilot_runtime,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = _local_now,
    ):
        self._device_flow = device_flow
        self._provisioner = provisioner
        self._pool = pool
        self._sandbox = sandbox
        self._external_integration_port = external_integration_port
        self._runtime_factory = runtime_factory
        self._clock = clock
        self._now = now
        self._catalogs: dict[str, tuple[float, list[CopilotModelEntry]]] = {}
        self._catalog_lock = asyncio.Lock()
        # Refresh rotates tokens while callers may still hold a superseded payload.
        self._current: Optional[ExternalIntegrationPayload] = None
        self._superseded: set[str] = set()
        self._refresh_lock = asyncio.Lock()
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
        self._current = payload

    async def teardown(self):
        self._catalogs.clear()
        self._current = None
        self._superseded.clear()
        await self._pool.invalidate(PROVIDER)

    async def list_models(
        self, credentials: Optional[ExternalIntegrationPayload]
    ) -> list[AIModel]:
        entries = await self._call(
            credentials, lambda token: self._catalog(token, max_age=0)
        )
        return [_to_model(entry) for entry in entries if entry.enabled]

    async def get_model(
        self, model_id: str, credentials: Optional[ExternalIntegrationPayload]
    ) -> Optional[AIModel]:
        entry = await self._call(credentials, lambda token: self._find(token, model_id))
        return _to_model(entry) if entry else None

    async def generate(
        self, request: AIGenerationRequest, credentials: ExternalIntegrationPayload
    ) -> AIGeneration:
        text = await self._call(
            credentials, lambda token: self._complete(request, token)
        )
        if not text:
            return AIGeneration(status=AIGenerationStatus.INCOMPLETE)
        return AIGeneration(status=AIGenerationStatus.COMPLETED, text=text)

    async def _complete(
        self, request: AIGenerationRequest, token: str
    ) -> Optional[str]:
        entry = await self._find(token, request.model)
        if entry is None:
            raise AIProviderError(
                AIProviderErrorCode.MODEL_NOT_FOUND,
                f"Model {request.model} is not available in GitHub Copilot",
            )

        async with self._runtime(token) as runtime:
            return await runtime.complete(
                model=entry.id,
                instructions=request.instructions,
                prompt="\n\n".join(message.content for message in request.messages),
                schema=request.response_schema.schema
                if request.response_schema
                else None,
                reasoning_effort=_reasoning_effort(entry, request.reasoning_effort),
                timeout=GENERATION_TIMEOUT_SECONDS,
            )

    async def _call(
        self,
        credentials: Optional[ExternalIntegrationPayload],
        operation: Callable[[str], Awaitable[T]],
    ) -> T:
        credentials = await self._credentials(credentials)
        can_refresh = bool(credentials.get("refresh_token"))
        while True:
            token = credentials["access_token"]
            try:
                return await operation(token)
            except CopilotRuntimeUnavailable as e:
                raise AIProviderError(
                    AIProviderErrorCode.UNAVAILABLE,
                    "GitHub Copilot runtime is not available",
                ) from e
            except CopilotRuntimeError as e:
                if not can_refresh or e.kind != CopilotErrorKind.AUTH:
                    raise await self._provider_error(token, e) from e
            can_refresh = False
            await self._pool.discard(PROVIDER, token)
            credentials = await self._refresh(credentials)

    async def _credentials(
        self, credentials: Optional[ExternalIntegrationPayload]
    ) -> ExternalIntegrationPayload:
        if not (credentials or {}).get("access_token"):
            raise AIProviderError(
                AIProviderErrorCode.INVALID_CREDENTIALS,
                "GitHub Copilot is not connected",
            )
        if self._is_superseded(credentials):
            credentials = self._current

        expiry = credentials.get("expires_at")
        if not credentials.get("refresh_token") or not expiry:
            return credentials
        expires_at = datetime.fromisoformat(expiry)
        now = self._now()
        if expires_at - now > TOKEN_REFRESH_MARGIN:
            return credentials
        try:
            return await self._refresh(credentials)
        except AIProviderError as e:
            if e.code != AIProviderErrorCode.UNAVAILABLE or now >= expires_at:
                raise
            self._log.warning("Could not refresh the GitHub Copilot token yet")
            return credentials

    async def _refresh(
        self, stale: ExternalIntegrationPayload
    ) -> ExternalIntegrationPayload:
        async with self._refresh_lock:
            if self._is_superseded(stale):
                return self._current
            fresh = await self._device_flow.refresh(stale["refresh_token"])
            await self._external_integration_port.update_payload(
                ExternalIntegrationId.GITHUB_COPILOT, fresh
            )
            self._superseded.add(self._pool.fingerprint(stale["refresh_token"]))
            self._current = fresh
            catalog = self._catalogs.pop(
                self._pool.fingerprint(stale["access_token"]), None
            )
            if catalog is not None:
                self._catalogs[self._pool.fingerprint(fresh["access_token"])] = catalog
            return fresh

    def _is_superseded(self, credentials: ExternalIntegrationPayload) -> bool:
        refresh_token = credentials.get("refresh_token")
        return (
            bool(refresh_token)
            and self._pool.fingerprint(refresh_token) in self._superseded
        )

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
            async with self._runtime(token) as runtime:
                entries = await runtime.list_models()
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


def _setup_error_code(kind: CopilotErrorKind) -> IntegrationSetupErrorCode:
    if kind == CopilotErrorKind.AUTH:
        return IntegrationSetupErrorCode.INVALID_CREDENTIALS
    if kind == CopilotErrorKind.FORBIDDEN:
        return IntegrationSetupErrorCode.NOT_ENTITLED
    if kind == CopilotErrorKind.RUNTIME:
        return IntegrationSetupErrorCode.RUNTIME_FAILED
    return IntegrationSetupErrorCode.UNREACHABLE
