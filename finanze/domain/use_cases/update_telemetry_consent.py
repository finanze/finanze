import abc

from domain.telemetry import TelemetryConsent


class UpdateTelemetryConsent(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, consent: TelemetryConsent) -> TelemetryConsent:
        raise NotImplementedError
