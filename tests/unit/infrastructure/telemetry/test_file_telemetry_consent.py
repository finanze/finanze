import json
from datetime import datetime

import pytest

from domain.telemetry import TelemetryConsent
from infrastructure.telemetry.file_telemetry_consent import (
    FILE_NAME,
    FileTelemetryConsent,
)


class TestFileTelemetryConsent:
    @pytest.mark.asyncio
    async def test_defaults_to_disabled_and_creates_install_id(self, tmp_path):
        adapter = FileTelemetryConsent(tmp_path)

        consent = await adapter.get()

        assert consent.error_reporting is False
        assert consent.install_id is not None
        assert (tmp_path / FILE_NAME).exists()

    @pytest.mark.asyncio
    async def test_install_id_is_stable_between_reads(self, tmp_path):
        adapter = FileTelemetryConsent(tmp_path)

        first = await adapter.get()
        second = await adapter.get()

        assert first.install_id == second.install_id

    @pytest.mark.asyncio
    async def test_saves_and_reads_back_consent(self, tmp_path):
        adapter = FileTelemetryConsent(tmp_path)
        updated_at = datetime.now().astimezone()

        await adapter.save(
            TelemetryConsent(error_reporting=True, updated_at=updated_at)
        )
        stored = await adapter.get()

        assert stored.error_reporting is True
        assert stored.updated_at == updated_at

    @pytest.mark.asyncio
    async def test_recovers_from_corrupted_file(self, tmp_path):
        (tmp_path / FILE_NAME).write_text("not json", encoding="utf-8")
        adapter = FileTelemetryConsent(tmp_path)

        consent = await adapter.get()

        assert consent.error_reporting is False
        assert consent.install_id is not None
        assert json.loads((tmp_path / FILE_NAME).read_text(encoding="utf-8"))

    @pytest.mark.asyncio
    async def test_creates_missing_directory(self, tmp_path):
        target = tmp_path / "nested" / "dir"
        adapter = FileTelemetryConsent(target)

        await adapter.get()

        assert (target / FILE_NAME).exists()
