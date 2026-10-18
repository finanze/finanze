import logging

import strictyaml

from application.ports.legacy_config_importer import LegacyConfigImporter
from infrastructure.repository.settings.settings_mapper import legacy_to_sections
from infrastructure.repository.settings.settings_repository import SettingsRepository


class LegacyConfigBackupImporter(LegacyConfigImporter):
    def __init__(self, settings_repository: SettingsRepository):
        self._settings_repository = settings_repository
        self._log = logging.getLogger(__name__)

    async def import_data(self, data: bytes):
        parsed = strictyaml.load(data.decode("utf-8")).data
        if not isinstance(parsed, dict):
            raise ValueError("Invalid legacy config backup payload")

        sections, last_update = legacy_to_sections(parsed)
        applied = await self._settings_repository.apply_legacy(sections, last_update)
        self._log.info(
            "Legacy config backup %s", "applied" if applied else "skipped, not newer"
        )
