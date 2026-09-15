from typing import Optional

from application.ports.error_reporter_port import ErrorReporterPort
from domain.telemetry import TelemetryContext, TelemetryLevel


class NoopErrorReporter(ErrorReporterPort):
    def set_enabled(self, enabled: bool):
        pass

    def set_context(self, context: TelemetryContext):
        pass

    def set_user(self, user_hash: Optional[str]):
        pass

    def capture_exception(
        self,
        exc: BaseException,
        *,
        tags: Optional[dict[str, str]] = None,
        extra: Optional[dict] = None,
        level: TelemetryLevel = TelemetryLevel.ERROR,
    ):
        pass

    async def flush(self):
        pass
