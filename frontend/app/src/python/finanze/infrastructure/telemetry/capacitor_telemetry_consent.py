import json
import logging
from datetime import datetime
from uuid import UUID, uuid4

from js import jsBridge

from application.ports.telemetry_consent_port import TelemetryConsentPort
from domain.telemetry import TelemetryConsent

PREFS_KEY = "telemetry_consent"


class CapacitorTelemetryConsent(TelemetryConsentPort):
    def __init__(self):
        self._log = logging.getLogger(__name__)

    async def get(self) -> TelemetryConsent:
        raw = await jsBridge.preferences.get(PREFS_KEY)

        data = None
        if raw:
            try:
                data = json.loads(raw)
            except ValueError:
                self._log.warning("Invalid telemetry consent stored, resetting it")

        if not isinstance(data, dict):
            return await self.save(TelemetryConsent(install_id=uuid4()))

        install_id = data.get("installId")
        updated_at = data.get("updatedAt")

        try:
            parsed_id = UUID(install_id) if install_id else uuid4()
        except ValueError:
            parsed_id = uuid4()

        return TelemetryConsent(
            error_reporting=data.get("errorReporting") is True,
            session_replay=data.get("sessionReplay") is True,
            install_id=parsed_id,
            updated_at=datetime.fromisoformat(updated_at) if updated_at else None,
        )

    async def save(self, consent: TelemetryConsent) -> TelemetryConsent:
        if consent.install_id is None:
            consent.install_id = uuid4()

        payload = {
            "errorReporting": consent.error_reporting,
            "sessionReplay": consent.session_replay,
            "installId": str(consent.install_id),
            "updatedAt": consent.updated_at.isoformat() if consent.updated_at else None,
        }

        await jsBridge.preferences.set(PREFS_KEY, json.dumps(payload))

        return consent
