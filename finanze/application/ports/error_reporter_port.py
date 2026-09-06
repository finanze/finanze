import abc
from typing import Optional

from domain.telemetry import TelemetryContext, TelemetryLevel


class ErrorReporterPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def set_enabled(self, enabled: bool):
        raise NotImplementedError

    @abc.abstractmethod
    def set_context(self, context: TelemetryContext):
        raise NotImplementedError

    @abc.abstractmethod
    def set_user(self, user_hash: Optional[str]):
        raise NotImplementedError

    @abc.abstractmethod
    def capture_exception(
        self,
        exc: BaseException,
        *,
        tags: Optional[dict[str, str]] = None,
        extra: Optional[dict] = None,
        level: TelemetryLevel = TelemetryLevel.ERROR,
    ):
        raise NotImplementedError

    @abc.abstractmethod
    async def flush(self):
        raise NotImplementedError
