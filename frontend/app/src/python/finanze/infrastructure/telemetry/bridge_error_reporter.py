import json
import linecache
import logging
import traceback
from typing import Optional

import js

from application.ports.error_reporter_port import ErrorReporterPort
from domain.exception.reporting import is_reportable
from domain.platform import OS_NAMES
from domain.telemetry import TelemetryContext, TelemetryLevel
from infrastructure.telemetry.scrubbing import scrub, scrub_text

_LEVELS = {
    TelemetryLevel.ERROR: "error",
    TelemetryLevel.WARNING: "warning",
    TelemetryLevel.INFO: "info",
}

MAX_FRAMES = 30
MAX_CAUSES = 3
MAX_CONTEXT_LENGTH = 400
CONTEXT_PADDING = 120


def _relative_filename(filename: str) -> str:
    marker = "/python/"
    if marker in filename:
        return filename.split(marker, 1)[1]
    return filename


# Positions come as UTF-8 byte offsets, the same conversion the traceback module does
def _char_offset(line: str, byte_offset: Optional[int]) -> Optional[int]:
    if byte_offset is None:
        return None
    return len(line.encode("utf-8")[:byte_offset].decode("utf-8", errors="replace"))


def _frame_source(frame) -> tuple[Optional[str], Optional[int], Optional[dict]]:
    # Columns index the raw line, while frame.line comes already stripped
    raw = getattr(frame, "_original_line", None) or linecache.getline(
        frame.filename, frame.lineno
    )
    line = (raw or frame.line or "").rstrip()
    if not line:
        return None, None, None

    colno = _char_offset(line, getattr(frame, "colno", None))
    end_colno = _char_offset(line, getattr(frame, "end_colno", None))
    spans_one_line = getattr(frame, "end_lineno", frame.lineno) == frame.lineno

    if (
        not raw
        or colno is None
        or end_colno is None
        or end_colno <= colno
        or end_colno > len(line)
        or not spans_one_line
    ):
        return scrub_text(line.strip()[:MAX_CONTEXT_LENGTH]), None, None

    frame_vars = {
        "expression": scrub_text(line[colno:end_colno][:MAX_CONTEXT_LENGTH]),
        "columns": f"{colno}-{end_colno}",
    }

    if len(line) <= MAX_CONTEXT_LENGTH:
        return scrub_text(line), colno + 1, frame_vars

    # Minified lines get cut around the failing span, so the column is rebased on it
    start = max(0, min(colno - CONTEXT_PADDING, len(line) - MAX_CONTEXT_LENGTH))
    end = start + MAX_CONTEXT_LENGTH
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(line) else ""

    return (
        scrub_text(prefix + line[start:end] + suffix),
        colno - start + len(prefix) + 1,
        frame_vars,
    )


def _exception_entry(exc: BaseException) -> dict:
    summary = traceback.TracebackException.from_exception(exc)

    frames = []
    for frame in summary.stack[-MAX_FRAMES:]:
        context_line, colno, frame_vars = _frame_source(frame)
        entry = {
            "filename": _relative_filename(frame.filename),
            "function": frame.name,
            "lineno": frame.lineno,
            "context_line": context_line,
        }
        if colno is not None:
            entry["colno"] = colno
        if frame_vars:
            entry["vars"] = frame_vars
        frames.append(entry)

    return {
        "type": type(exc).__name__,
        "value": scrub_text(str(exc)),
        "frames": frames,
    }


def _cause_chain(exc: BaseException) -> list[BaseException]:
    chain = [exc]
    seen = {id(exc)}
    current = exc

    while len(chain) <= MAX_CAUSES:
        nxt = current.__cause__
        if nxt is None and not current.__suppress_context__:
            nxt = current.__context__
        if nxt is None or id(nxt) in seen:
            break
        chain.append(nxt)
        seen.add(id(nxt))
        current = nxt

    return chain


def get_environment() -> str:
    try:
        return js.jsBridge.telemetry.environment or "production"
    except Exception:
        return "production"


class BridgeErrorReporter(ErrorReporterPort):
    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._enabled = False
        self._context: Optional[TelemetryContext] = None

    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    def set_context(self, context: TelemetryContext):
        self._context = context

    def set_user(self, user_hash: Optional[str]):
        if self._context:
            self._context.user_hash = user_hash

    def capture_exception(
        self,
        exc: BaseException,
        *,
        tags: Optional[dict[str, str]] = None,
        extra: Optional[dict] = None,
        level: TelemetryLevel = TelemetryLevel.ERROR,
    ):
        if not self._enabled or not is_reportable(exc):
            return

        try:
            payload = self._build_payload(exc, tags, extra, level)
            js.jsBridge.telemetry.capture(json.dumps(payload))
        except Exception:
            self._log.debug("Failed to report exception", exc_info=True)

    async def flush(self):
        pass

    def _build_payload(self, exc, tags, extra, level) -> dict:
        chain = _cause_chain(exc)

        all_tags = {"component": "mobile-backend"}
        context = self._context
        os_context = None
        if context:
            if context.operative_system:
                all_tags["platform_os"] = context.operative_system.value
                os_context = {
                    "name": OS_NAMES[context.operative_system],
                    "version": context.os_version,
                }
            if context.os_version:
                all_tags["os_version"] = context.os_version
            if context.distribution:
                all_tags["distribution"] = context.distribution.value
            if context.user_hash:
                all_tags["user_id"] = context.user_hash
        if tags:
            all_tags.update({k: str(v) for k, v in tags.items()})

        payload = {
            **_exception_entry(exc),
            "level": _LEVELS[level],
            "tags": all_tags,
            "extra": scrub(extra) if extra else None,
            "release": context.release if context else None,
            "user_id": context.user_hash if context else None,
            "os": os_context,
        }

        # Sentry renders the last value as the title, so causes go root-first.
        if len(chain) > 1:
            payload["causes"] = [_exception_entry(c) for c in reversed(chain[1:])]

        return payload
