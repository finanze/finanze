from application.ports.telemetry_consent_port import TelemetryConsentPort
from domain.telemetry import TelemetryConsent
from domain.use_cases.get_telemetry_consent import GetTelemetryConsent


class GetTelemetryConsentImpl(GetTelemetryConsent):
    def __init__(self, consent_port: TelemetryConsentPort):
        self._consent_port = consent_port

    async def execute(self) -> TelemetryConsent:
        return await self._consent_port.get()
