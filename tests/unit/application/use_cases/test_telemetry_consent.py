from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from application.use_cases.get_telemetry_consent import GetTelemetryConsentImpl
from application.use_cases.update_telemetry_consent import UpdateTelemetryConsentImpl
from domain.telemetry import TelemetryConsent


def _consent_port(current: TelemetryConsent) -> AsyncMock:
    port = AsyncMock()
    port.get.return_value = current
    port.save.side_effect = lambda consent: consent
    return port


class TestGetTelemetryConsent:
    @pytest.mark.asyncio
    async def test_returns_stored_consent(self):
        stored = TelemetryConsent(error_reporting=True, install_id=uuid4())
        use_case = GetTelemetryConsentImpl(_consent_port(stored))

        assert await use_case.execute() == stored


class TestUpdateTelemetryConsent:
    @pytest.mark.asyncio
    async def test_persists_and_enables_reporter(self):
        install_id = uuid4()
        port = _consent_port(TelemetryConsent(install_id=install_id))
        reporter = MagicMock()
        use_case = UpdateTelemetryConsentImpl(port, reporter)

        saved = await use_case.execute(TelemetryConsent(error_reporting=True))

        assert saved.error_reporting is True
        assert saved.install_id == install_id
        assert saved.updated_at is not None
        port.save.assert_awaited_once()
        reporter.set_enabled.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_disabling_stops_the_reporter(self):
        port = _consent_port(TelemetryConsent(error_reporting=True, install_id=uuid4()))
        reporter = MagicMock()
        use_case = UpdateTelemetryConsentImpl(port, reporter)

        await use_case.execute(TelemetryConsent(error_reporting=False))

        reporter.set_enabled.assert_called_once_with(False)
