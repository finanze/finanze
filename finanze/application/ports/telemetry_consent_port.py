import abc

from domain.telemetry import TelemetryConsent


class TelemetryConsentPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get(self) -> TelemetryConsent:
        raise NotImplementedError

    @abc.abstractmethod
    async def save(self, consent: TelemetryConsent) -> TelemetryConsent:
        raise NotImplementedError
