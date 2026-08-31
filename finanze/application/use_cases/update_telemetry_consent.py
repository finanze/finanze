from datetime import datetime

from application.ports.error_reporter_port import ErrorReporterPort
from application.ports.telemetry_consent_port import TelemetryConsentPort
from domain.telemetry import TelemetryConsent
from domain.use_cases.update_telemetry_consent import UpdateTelemetryConsent


class UpdateTelemetryConsentImpl(UpdateTelemetryConsent):
    def __init__(
        self,
        consent_port: TelemetryConsentPort,
        error_reporter: ErrorReporterPort,
    ):
        self._consent_port = consent_port
        self._error_reporter = error_reporter

    async def execute(self, consent: TelemetryConsent) -> TelemetryConsent:
        current = await self._consent_port.get()

        error_reporting = consent.error_reporting
        updated = TelemetryConsent(
            error_reporting=error_reporting,
            session_replay=consent.session_replay and error_reporting,
            install_id=current.install_id,
            updated_at=datetime.now().astimezone(),
        )

        saved = await self._consent_port.save(updated)
        self._error_reporter.set_enabled(saved.error_reporting)
        return saved
