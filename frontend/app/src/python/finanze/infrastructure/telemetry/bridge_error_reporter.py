import json
import logging
import traceback
from typing import Optional

import js

from application.ports.error_reporter_port import ErrorReporterPort
from domain.exception.reporting import is_reportable
from domain.telemetry import TelemetryContext, TelemetryLevel
from infrastructure.telemetry.scrubbing import scrub, scrub_text

_LEVELS = {
    TelemetryLevel.ERROR: "error",
    TelemetryLevel.WARNING: "warning",
    TelemetryLevel.INFO: "info",
}

MAX_FRAMES = 30


def _relative_filename(filename: str) -> str:
    marker = "/python/"
    if marker in filename:
        return filename.split(marker, 1)[1]
    return filename


class BridgeErrorReporter(ErrorReporterPort):
    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._enabled = False
        self._context: Optional[TelemetryContext] = None

    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    def set_context(self, context: TelemetryContext):
        self._context = context

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
        summary = traceback.TracebackException.from_exception(exc)

        frames = [
            {
                "filename": _relative_filename(frame.filename),
                "function": frame.name,
                "lineno": frame.lineno,
                "context_line": scrub_text(frame.line) if frame.line else None,
            }
            for frame in summary.stack
        ][-MAX_FRAMES:]

        all_tags = {"component": "mobile-backend"}
        context = self._context
        if context:
            if context.operative_system:
                all_tags["platform_os"] = context.operative_system.value
            if context.user_hash:
                all_tags["user_hash"] = context.user_hash
        if tags:
            all_tags.update({k: str(v) for k, v in tags.items()})

        return {
            "type": type(exc).__name__,
            "value": scrub_text(str(exc)),
            "level": _LEVELS[level],
            "frames": frames,
            "tags": all_tags,
            "extra": scrub(extra) if extra else None,
            "release": context.release if context else None,
        }
