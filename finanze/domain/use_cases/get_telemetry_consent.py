import abc

from domain.telemetry import TelemetryConsent


class GetTelemetryConsent(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> TelemetryConsent:
        raise NotImplementedError
