import json
import logging
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from application.ports.telemetry_consent_port import TelemetryConsentPort
from domain.telemetry import TelemetryConsent

FILE_NAME = "telemetry.json"


class FileTelemetryConsent(TelemetryConsentPort):
    def __init__(self, data_dir: str | Path):
        self._log = logging.getLogger(__name__)
        self._path = Path(data_dir) / FILE_NAME

    async def get(self) -> TelemetryConsent:
        raw = self._read()
        if raw is None:
            return await self.save(TelemetryConsent(install_id=uuid4()))

        install_id = raw.get("install_id")
        updated_at = raw.get("updated_at")

        consent = TelemetryConsent(
            error_reporting=bool(raw.get("error_reporting", False)),
            session_replay=bool(raw.get("session_replay", False)),
            install_id=UUID(install_id) if install_id else None,
            updated_at=datetime.fromisoformat(updated_at) if updated_at else None,
        )

        if consent.install_id is None:
            consent.install_id = uuid4()
            return await self.save(consent)

        return consent

    async def save(self, consent: TelemetryConsent) -> TelemetryConsent:
        if consent.install_id is None:
            consent.install_id = uuid4()

        payload = {
            "error_reporting": consent.error_reporting,
            "session_replay": consent.session_replay,
            "install_id": str(consent.install_id),
            "updated_at": consent.updated_at.isoformat()
            if consent.updated_at
            else None,
        }

        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        return consent

    def _read(self) -> dict | None:
        if not self._path.exists():
            return None

        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            self._log.warning("Invalid telemetry consent file, resetting it")
            return None
