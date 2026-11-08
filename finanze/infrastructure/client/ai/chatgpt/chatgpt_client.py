import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Awaitable, Callable, Optional, TypeVar

from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.oauth_connectable_integration import (
    OAuthConnectableIntegration,
)
from dateutil.tz import tzlocal
from domain.ai import (
    AIClientFeature,
    AIGeneration,
    AIGenerationRequest,
    AIGenerationStatus,
    AIModel,
    AIModelCapability,
)
from domain.exception.exceptions import (
    AIProviderError,
    AIProviderErrorCode,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
    TooManyRequests,
)
from domain.external_integration import (
    CompleteExternalIntegrationConnectionRequest,
    ExternalIntegrationId,
    ExternalIntegrationPayload,
)

from infrastructure.client.ai.chatgpt.chatgpt_oauth import ChatGPTOAuth
from infrastructure.client.ai.http_ai_client import HttpAIClient
from infrastructure.client.ai.reasoning_levels import pick_reasoning_level
from infrastructure.client.ai.responses_api import (
    parse_response_output,
    parse_stream_events,
)
from infrastructure.client.http.http_response import HttpResponse

CHATGPT = ExternalIntegrationId.CHATGPT
CATALOG_TTL_SECONDS = 120
TOKEN_REFRESH_MARGIN = timedelta(minutes=5)
MAX_CALL_ATTEMPTS = 3
NOT_ELIGIBLE = "subscription_sharing_user_not_eligible"
USAGE_LIMIT_CODES = {"subscription_sharing_usage_limit_exceeded"}
UNAUTHORIZED_CODES = {"subscription_sharing_invalid_user"}
FORBIDDEN_CODES = {
    NOT_ELIGIBLE,
    "chatpass_v2_scope_not_authorized",
    "chatpass_v2_invalid_authorization_context",
}
UNSUPPORTED_CODES = {
    "subscription_sharing_unsupported_capability",
    "subscription_sharing_route_not_supported",
}
MODEL_NOT_FOUND_CODES = {"model_not_found"}

T = TypeVar("T")


@dataclass(frozen=True)
class ChatGPTModelEntry:
    slug: str
    name: str
    efforts: tuple[str, ...] = ()


class _Unauthorized(Exception):
    pass


def _local_now() -> datetime:
    return datetime.now(tzlocal())


def _fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _instant(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _reasoning_levels(raw) -> tuple[str, ...]:
    levels = []
    for item in raw if isinstance(raw, list) else []:
        level = item.get("effort") if isinstance(item, dict) else item
        if isinstance(level, str) and level and level not in levels:
            levels.append(level)
    return tuple(levels)


def _parse_models(data) -> list[ChatGPTModelEntry]:
    models = data.get("models") if isinstance(data, dict) else None
    entries = []
    for item in models if isinstance(models, list) else []:
        if not isinstance(item, dict) or item.get("visibility") != "list":
            continue
        slug = item.get("slug")
        if not isinstance(slug, str) or not slug:
            continue
        name = item.get("display_name")
        entries.append(
            ChatGPTModelEntry(
                slug=slug,
                name=name if isinstance(name, str) and name else slug,
                efforts=_reasoning_levels(item.get("supported_reasoning_levels")),
            )
        )
    return entries


def _to_model(entry: ChatGPTModelEntry) -> AIModel:
    capabilities = {AIModelCapability.STRUCTURED_OUTPUT}
    if entry.efforts:
        capabilities.add(AIModelCapability.REASONING)
    return AIModel(id=entry.slug, name=entry.name, capabilities=capabilities)


def _error_for_code(code: Optional[str], message: str) -> Optional[Exception]:
    if code in USAGE_LIMIT_CODES:
        return AIProviderError(
            AIProviderErrorCode.INSUFFICIENT_FUNDS, "ChatGPT usage limit reached"
        )
    if code in UNAUTHORIZED_CODES:
        return _Unauthorized(code)
    if code in FORBIDDEN_CODES:
        return AIProviderError(
            AIProviderErrorCode.INVALID_CREDENTIALS,
            "The connected ChatGPT account can't use its plan in Finanze",
        )
    if code in UNSUPPORTED_CODES:
        return AIProviderError(AIProviderErrorCode.UNSUPPORTED_OPERATION, message)
    if code in MODEL_NOT_FOUND_CODES:
        return AIProviderError(
            AIProviderErrorCode.MODEL_NOT_FOUND,
            "The selected model is no longer available in ChatGPT",
        )
    return None


class ChatGPTClient(HttpAIClient, OAuthConnectableIntegration):
    PROVIDER_NAME = "ChatGPT"
    BASE_URL = "https://api.openai.com/v1"
    REQUEST_TIMEOUT_SECONDS = 120.0
    RETRYABLE_STATUSES = (500, 502, 503, 504)

    def __init__(
        self,
        oauth: ChatGPTOAuth,
        external_integration_port: ExternalIntegrationPort,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = _local_now,
    ):
        super().__init__()
        self._oauth = oauth
        self._external_integration_port = external_integration_port
        self._clock = clock
        self._now = now
        self._catalogs: dict[str, tuple[float, list[ChatGPTModelEntry]]] = {}
        self._catalog_lock = asyncio.Lock()
        # Refresh rotates tokens while callers may still hold a superseded payload.
        self._current: Optional[ExternalIntegrationPayload] = None
        self._superseded: set[str] = set()
        self._refresh_lock = asyncio.Lock()
        self._log = logging.getLogger(__name__)

    def features(self) -> set[AIClientFeature]:
        return {AIClientFeature.GENERATION, AIClientFeature.MODEL_LISTING}

    async def start_authorization(
        self, payload: ExternalIntegrationPayload, completion_url: Optional[str]
    ) -> str:
        previous = await self._external_integration_port.get_payload(
            CHATGPT, include_expired=True
        )
        return await self._oauth.start(completion_url, previous)

    async def complete_authorization(
        self, request: CompleteExternalIntegrationConnectionRequest
    ) -> ExternalIntegrationPayload:
        payload = await self._oauth.complete(request)
        response = await self._request("GET", "/models", payload)
        if not response.ok:
            code, _ = await self._error_details(response)
            self._log.warning(
                f"ChatGPT plan access check failed: {response.status} {code}"
            )
            if code == NOT_ELIGIBLE or response.status == 403:
                raise IntegrationSetupError(IntegrationSetupErrorCode.NOT_ENTITLED)
            if response.status == 401:
                raise IntegrationSetupError(
                    IntegrationSetupErrorCode.INVALID_CREDENTIALS
                )
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNREACHABLE)

        self._reset()
        self._catalogs[payload["client_id"]] = (
            self._clock(),
            _parse_models(await response.json()),
        )
        self._current = payload
        return payload

    async def callback_destination(self, state: str) -> Optional[str]:
        return self._oauth.destination(state)

    async def teardown(self, payload: Optional[ExternalIntegrationPayload] = None):
        self._reset()
        if payload:
            await self._oauth.revoke(payload)

    async def list_models(
        self, credentials: Optional[ExternalIntegrationPayload]
    ) -> list[AIModel]:
        entries = await self._call(
            credentials, lambda current: self._catalog(current, max_age=0)
        )
        return [_to_model(entry) for entry in entries]

    async def get_model(
        self, model_id: str, credentials: Optional[ExternalIntegrationPayload]
    ) -> Optional[AIModel]:
        entry = await self._call(
            credentials, lambda current: self._find(current, model_id)
        )
        return _to_model(entry) if entry else None

    async def generate(
        self, request: AIGenerationRequest, credentials: ExternalIntegrationPayload
    ) -> AIGeneration:
        if request.upstream_provider:
            raise AIProviderError(
                AIProviderErrorCode.UNSUPPORTED_OPERATION,
                "ChatGPT does not support upstream providers",
            )
        return await self._call(
            credentials, lambda current: self._generate(request, current)
        )

    def _headers(self, credentials: Optional[ExternalIntegrationPayload]) -> dict:
        token = (credentials or {}).get("access_token")
        return {"Authorization": f"Bearer {token}"} if token else {}

    async def _generate(
        self, request: AIGenerationRequest, credentials: ExternalIntegrationPayload
    ) -> AIGeneration:
        entry = await self._find(credentials, request.model)
        if entry is None:
            raise AIProviderError(
                AIProviderErrorCode.MODEL_NOT_FOUND,
                f"Model {request.model} is not available in ChatGPT",
            )

        body = {
            "model": entry.slug,
            "input": [
                {"role": message.role.value.lower(), "content": message.content}
                for message in request.messages
            ],
            "store": False,
            "stream": True,
        }
        if request.instructions:
            body["instructions"] = request.instructions
        if request.response_schema is not None:
            body["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": request.response_schema.name,
                    "strict": True,
                    "schema": request.response_schema.schema,
                }
            }
        effort = pick_reasoning_level(entry.efforts, request.reasoning_effort)
        if effort:
            body["reasoning"] = {"effort": effort}

        response = await self._request("POST", "/responses", credentials, json=body)
        if not response.ok:
            raise await self._response_error(response, credentials)
        return self._stream_result(await response.text(), credentials)

    def _stream_result(
        self, body: str, credentials: ExternalIntegrationPayload
    ) -> AIGeneration:
        for event in parse_stream_events(body):
            kind = event.get("type")
            if kind in ("response.completed", "response.incomplete"):
                generation = parse_response_output(event.get("response") or {})
                if (
                    kind == "response.incomplete"
                    and generation.status == AIGenerationStatus.COMPLETED
                ):
                    generation.status = AIGenerationStatus.INCOMPLETE
                return generation
            if kind in ("response.failed", "error"):
                error = (
                    (event.get("response") or {}).get("error")
                    if kind == "response.failed"
                    else event.get("error") or event
                )
                error = error if isinstance(error, dict) else {}
                code = error.get("code")
                self._log.warning(f"ChatGPT response failed: {code}")
                mapped = _error_for_code(code, error.get("message") or str(code))
                if isinstance(mapped, _Unauthorized):
                    raise mapped
                if mapped is not None:
                    self._forget_catalog(mapped, credentials)
                    raise mapped
                raise AIProviderError(
                    AIProviderErrorCode.UNAVAILABLE, f"ChatGPT response failed ({code})"
                )
        raise AIProviderError(
            AIProviderErrorCode.UNAVAILABLE,
            "ChatGPT stream ended before the response completed",
        )

    async def _call(
        self,
        credentials: Optional[ExternalIntegrationPayload],
        operation: Callable[[ExternalIntegrationPayload], Awaitable[T]],
    ) -> T:
        current = await self._credentials(credentials)
        refreshed = False
        for _ in range(MAX_CALL_ATTEMPTS):
            try:
                return await operation(current)
            except _Unauthorized as e:
                if refreshed:
                    await self._expire()
                    raise AIProviderError(
                        AIProviderErrorCode.REAUTHENTICATION_REQUIRED,
                        "ChatGPT sign-in expired, sign in again",
                    ) from e
                current, refreshed = await self._refresh(current)
        await self._expire()
        raise AIProviderError(
            AIProviderErrorCode.REAUTHENTICATION_REQUIRED,
            "ChatGPT sign-in expired, sign in again",
        )

    async def _credentials(
        self, credentials: Optional[ExternalIntegrationPayload]
    ) -> ExternalIntegrationPayload:
        if not (credentials or {}).get("access_token"):
            raise AIProviderError(
                AIProviderErrorCode.INVALID_CREDENTIALS, "ChatGPT is not connected"
            )
        if self._is_superseded(credentials) and self._current is not None:
            credentials = self._current

        expires_at = _instant(credentials.get("expires_at"))
        now = self._now()
        if expires_at is None or expires_at - now > TOKEN_REFRESH_MARGIN:
            return credentials
        refresh_after = _instant(credentials.get("refresh_after"))
        if refresh_after is not None and now < refresh_after and now < expires_at:
            return credentials
        try:
            current, _ = await self._refresh(credentials)
            return current
        except AIProviderError as e:
            if e.code != AIProviderErrorCode.UNAVAILABLE or now >= expires_at:
                raise
            self._log.warning("Could not refresh the ChatGPT session yet")
            return credentials

    async def _refresh(
        self, stale: ExternalIntegrationPayload
    ) -> tuple[ExternalIntegrationPayload, bool]:
        async with self._refresh_lock:
            if self._is_superseded(stale) and self._current is not None:
                return self._current, False
            stored = await self._external_integration_port.get_payload(CHATGPT)
            if (
                stored
                and stored.get("refresh_token")
                and stored.get("refresh_token") != stale.get("refresh_token")
            ):
                self._replace(stale, stored)
                return stored, False
            try:
                fresh = await self._oauth.refresh(stale)
            except AIProviderError as e:
                if e.code == AIProviderErrorCode.REAUTHENTICATION_REQUIRED:
                    await self._expire_locked()
                raise
            await self._external_integration_port.update_payload(CHATGPT, fresh)
            self._replace(stale, fresh)
            return fresh, True

    def _replace(
        self, stale: ExternalIntegrationPayload, fresh: ExternalIntegrationPayload
    ):
        if stale.get("refresh_token"):
            self._superseded.add(_fingerprint(stale["refresh_token"]))
        self._current = fresh

    def _is_superseded(self, credentials: ExternalIntegrationPayload) -> bool:
        refresh_token = credentials.get("refresh_token")
        return bool(refresh_token) and _fingerprint(refresh_token) in self._superseded

    async def _expire(self):
        async with self._refresh_lock:
            await self._expire_locked()

    async def _expire_locked(self):
        self._log.warning("ChatGPT sign-in is no longer valid, marking it expired")
        await self._external_integration_port.expire(CHATGPT)
        self._reset()

    def _reset(self):
        self._catalogs.clear()
        self._current = None
        self._superseded.clear()

    async def _find(
        self, credentials: ExternalIntegrationPayload, model_id: str
    ) -> Optional[ChatGPTModelEntry]:
        entries = await self._catalog(credentials, max_age=CATALOG_TTL_SECONDS)
        return next((entry for entry in entries if entry.slug == model_id), None)

    async def _catalog(
        self, credentials: ExternalIntegrationPayload, max_age: float
    ) -> list[ChatGPTModelEntry]:
        key = credentials.get("client_id") or ""
        async with self._catalog_lock:
            cached = self._catalogs.get(key)
            if cached is not None and self._clock() - cached[0] < max_age:
                return cached[1]
            response = await self._request("GET", "/models", credentials)
            if not response.ok:
                raise await self._response_error(response, credentials)
            entries = _parse_models(await response.json())
            self._catalogs[key] = (self._clock(), entries)
            return entries

    def _forget_catalog(
        self, error: Exception, credentials: ExternalIntegrationPayload
    ):
        if (
            isinstance(error, AIProviderError)
            and error.code == AIProviderErrorCode.MODEL_NOT_FOUND
        ):
            self._catalogs.pop(credentials.get("client_id") or "", None)

    async def _response_error(
        self, response: HttpResponse, credentials: ExternalIntegrationPayload
    ) -> Exception:
        code, message = await self._error_details(response)
        self._log.warning(f"ChatGPT request failed: {response.status} {code}")
        mapped = _error_for_code(code, message or f"HTTP {response.status}")
        if mapped is not None:
            self._forget_catalog(mapped, credentials)
            return mapped
        if response.status == 401:
            return _Unauthorized(str(response.status))
        if response.status == 403:
            return AIProviderError(
                AIProviderErrorCode.INVALID_CREDENTIALS,
                message or "ChatGPT rejected the request",
            )
        if response.status == 429:
            return TooManyRequests()
        return AIProviderError(
            AIProviderErrorCode.UNAVAILABLE,
            f"ChatGPT request failed ({response.status})",
        )

    async def _error_details(
        self, response: HttpResponse
    ) -> tuple[Optional[str], Optional[str]]:
        try:
            body = await response.json()
        except Exception:
            return None, None
        if not isinstance(body, dict):
            return None, None
        error = body.get("error")
        if isinstance(error, dict):
            code = error.get("code") or error.get("type")
            return (str(code) if code else None), error.get("message")
        detail = body.get("detail")
        return None, detail if isinstance(detail, str) else None
