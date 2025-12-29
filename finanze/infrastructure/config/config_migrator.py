import logging
from copy import deepcopy

from infrastructure.config.base_config import CURRENT_VERSION
from infrastructure.config.versions import (
    migrate_v1_to_v2,
    migrate_v2_to_v3,
    migrate_v3_to_v4,
    migrate_v4_to_v5,
    migrate_v5_to_v6,
)


class ConfigMigrator:
    def __init__(self):
        self._log = logging.getLogger(__name__)
        self.migrations = {
            1: migrate_v1_to_v2,
            2: migrate_v2_to_v3,
            3: migrate_v3_to_v4,
            4: migrate_v4_to_v5,
            5: migrate_v5_to_v6,
        }

    def migrate(self, data: dict) -> tuple[dict, bool]:
        if data.get("version") == CURRENT_VERSION:
            return data, False

        migrated_data = deepcopy(data)
        if "version" not in migrated_data:
            self._log.info("No config version found, assuming version 1.")
            version = 1
        else:
            version = int(migrated_data["version"])

        was_migrated = False
        while version in self.migrations:
            self._log.info(f"Migrating config from version {version} to {version + 1}.")
            migrated_data = self.migrations[version](migrated_data)
            version = int(migrated_data["version"])
            was_migrated = True

        if was_migrated:
            self._log.info(f"Config migrated to version {version}")

        return migrated_data, was_migrated
