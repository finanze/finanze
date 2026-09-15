import logging
from typing import Optional

from application.ports.error_reporter_port import ErrorReporterPort
from domain.exception.reporting import is_reportable
from domain.platform import OS_NAMES
from domain.telemetry import TelemetryContext, TelemetryLevel
from infrastructure.telemetry.scrubbing import scrub, scrub_text

_SENTRY_LEVELS = {
    TelemetryLevel.ERROR: "error",
    TelemetryLevel.WARNING: "warning",
    TelemetryLevel.INFO: "info",
}


class SentryErrorReporter(ErrorReporterPort):
    def __init__(
        self,
        dsn: Optional[str],
        environment: str,
        release: Optional[str] = None,
    ):
        self._log = logging.getLogger(__name__)
        self._dsn = dsn
        self._environment = environment
        self._release = release
        self._enabled = False
        self._started = False
        self._context: Optional[TelemetryContext] = None

    def set_enabled(self, enabled: bool):
        if enabled == self._enabled:
            return

        self._enabled = enabled

        if not self._dsn:
            return

        if enabled:
            self._start()
        else:
            self._stop()

    def set_context(self, context: TelemetryContext):
        self._context = context
        if self._started:
            self._apply_context()

    def set_user(self, user_hash: Optional[str]):
        if self._context:
            self._context.user_hash = user_hash
        if self._started:
            self._apply_context()

    def capture_exception(
        self,
        exc: BaseException,
        *,
        tags: Optional[dict[str, str]] = None,
        extra: Optional[dict] = None,
        level: TelemetryLevel = TelemetryLevel.ERROR,
    ):
        if not self._enabled or not self._started:
            return

        if not is_reportable(exc):
            return

        try:
            import sentry_sdk

            with sentry_sdk.new_scope() as scope:
                scope.level = _SENTRY_LEVELS[level]
                for key, value in (tags or {}).items():
                    scope.set_tag(key, str(value))
                if extra:
                    scope.set_context("details", scrub(extra))
                sentry_sdk.capture_exception(exc)
        except Exception:
            self._log.debug("Failed to report exception", exc_info=True)

    async def flush(self):
        if not self._started:
            return

        try:
            import sentry_sdk

            sentry_sdk.flush(timeout=2)
        except Exception:
            self._log.debug("Failed to flush error reports", exc_info=True)

    def _start(self):
        try:
            import sentry_sdk
            from sentry_sdk.integrations.logging import LoggingIntegration

            sentry_sdk.init(
                dsn=self._dsn,
                environment=self._environment,
                release=self._release,
                send_default_pii=False,
                include_local_variables=False,
                max_request_body_size="never",
                attach_stacktrace=False,
                traces_sample_rate=0.0,
                shutdown_timeout=2,
                auto_enabling_integrations=False,
                integrations=[LoggingIntegration(level=logging.INFO, event_level=None)],
                before_send=self._before_send,
                before_breadcrumb=self._before_breadcrumb,
            )
            self._started = True
            self._apply_context()
            self._log.info("Error reporting enabled")
        except Exception:
            self._log.warning("Could not enable error reporting", exc_info=True)

    def _stop(self):
        if not self._started:
            return

        try:
            import sentry_sdk

            sentry_sdk.get_client().close(timeout=1)
        except Exception:
            self._log.debug("Failed to stop error reporting", exc_info=True)
        finally:
            self._started = False
            self._log.info("Error reporting disabled")

    def _apply_context(self):
        context = self._context
        if not context:
            return

        try:
            import sentry_sdk

            scope = sentry_sdk.get_global_scope()
            scope.set_tag("component", "backend")
            if context.operative_system:
                scope.set_tag("platform_os", context.operative_system.value)
                scope.set_context(
                    "os",
                    {
                        "name": OS_NAMES[context.operative_system],
                        "version": context.os_version,
                    },
                )
            if context.os_version:
                scope.set_tag("os_version", context.os_version)
            if context.distribution:
                scope.set_tag("distribution", context.distribution.value)

            user = {}
            if context.install_id:
                user["id"] = str(context.install_id)
            if context.user_hash:
                user["user_id"] = context.user_hash
            scope.set_user(user or None)

            if context.user_hash:
                scope.set_tag("user_id", context.user_hash)
            else:
                scope.remove_tag("user_id")
        except Exception:
            self._log.debug("Failed to apply telemetry context", exc_info=True)

    def _before_send(self, event, hint):
        if not self._enabled:
            return None

        exc_info = hint.get("exc_info") if hint else None
        if exc_info and not is_reportable(exc_info[1]):
            return None

        event.pop("server_name", None)
        event.pop("modules", None)

        for section in ("extra", "contexts", "tags", "request"):
            if section in event:
                event[section] = scrub(event[section])

        for entry in event.get("exception", {}).get("values", []):
            if "value" in entry and isinstance(entry["value"], str):
                entry["value"] = scrub_text(entry["value"])

        if isinstance(event.get("message"), str):
            event["message"] = scrub_text(event["message"])

        return event

    def _before_breadcrumb(self, crumb, hint):
        if not self._enabled:
            return None

        if isinstance(crumb.get("message"), str):
            crumb["message"] = scrub_text(crumb["message"])
        if "data" in crumb:
            crumb["data"] = scrub(crumb["data"])

        return crumb
