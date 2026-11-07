import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Protocol

from domain.ai import AIModelPricing

PROCESS_FAILURES = (
    "ProcessExitedError",
    "BrokenPipeError",
    "ConnectionResetError",
    "EOFError",
)


class CopilotErrorKind(str, Enum):
    AUTH = "AUTH"
    FORBIDDEN = "FORBIDDEN"
    QUOTA = "QUOTA"
    RATE_LIMIT = "RATE_LIMIT"
    MODEL = "MODEL"
    SCHEMA = "SCHEMA"
    RUNTIME = "RUNTIME"
    UNAVAILABLE = "UNAVAILABLE"


class CopilotRuntimeError(Exception):
    def __init__(self, kind: CopilotErrorKind, message: str):
        self.kind = kind
        super().__init__(message)


@dataclass(frozen=True)
class CopilotModelEntry:
    id: str
    name: str
    enabled: bool
    reasoning_efforts: tuple[str, ...] = ()
    pricing: Optional[AIModelPricing] = None


class CopilotRuntimeHandle(Protocol):
    async def stop(self) -> None: ...

    async def is_authenticated(self) -> bool: ...

    async def list_models(self) -> list[CopilotModelEntry]: ...

    async def complete(
        self,
        model: str,
        instructions: Optional[str],
        prompt: str,
        schema: Optional[dict],
        reasoning_effort: Optional[str],
        timeout: float,
    ) -> Optional[str]: ...


def classify_copilot_error(
    error: BaseException, session_error: Any = None
) -> CopilotErrorKind:
    if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
        return CopilotErrorKind.UNAVAILABLE
    if type(error).__name__ in PROCESS_FAILURES:
        return CopilotErrorKind.RUNTIME

    status, remediation, text = _error_facts(error, session_error)
    if (
        remediation == "sign_in"
        or status == 401
        or _mentions(
            text,
            "unauthorized",
            "bad credentials",
            "not authenticated",
            "unauthenticated",
        )
    ):
        return CopilotErrorKind.AUTH
    if status == 429 or _mentions(
        text, "rate limit", "rate_limit", "too many requests"
    ):
        return CopilotErrorKind.RATE_LIMIT
    if status == 402 or _mentions(
        text, "quota", "credit", "premium request", "insufficient", "billing", "budget"
    ):
        return CopilotErrorKind.QUOTA
    if status == 404 or (
        "model" in text
        and _mentions(
            text,
            "not found",
            "not available",
            "not supported",
            "unsupported",
            "unknown",
            "disabled",
            "invalid",
        )
    ):
        return CopilotErrorKind.MODEL
    if (
        remediation == "switch_account"
        or status == 403
        or _mentions(
            text, "forbidden", "not entitled", "no access", "subscription", "seat"
        )
    ):
        return CopilotErrorKind.FORBIDDEN
    if _mentions(
        text, "structured", "json_schema", "response_format", "responseformat"
    ):
        return CopilotErrorKind.SCHEMA
    return CopilotErrorKind.UNAVAILABLE


def _error_facts(
    error: BaseException, session_error: Any
) -> tuple[Optional[int], Optional[str], str]:
    status = None
    remediation = None
    parts = [str(error)]

    if session_error is not None:
        status = _as_int(getattr(session_error, "status_code", None))
        remediation = _enum_value(getattr(session_error, "remediation", None))
        for attribute in ("error_type", "error_code", "message"):
            parts.append(str(getattr(session_error, attribute, None) or ""))

    data = getattr(error, "data", None)
    if isinstance(data, dict):
        status = status or _as_int(data.get("statusCode") or data.get("status"))
        remediation = remediation or _enum_value(data.get("remediation"))
        for key in ("errorType", "errorCode", "message", "code"):
            parts.append(str(data.get(key) or ""))

    return status, remediation, " ".join(parts).lower()


def _mentions(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


def _as_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _enum_value(value: Any) -> Optional[str]:
    value = getattr(value, "value", value)
    return value if isinstance(value, str) else None
