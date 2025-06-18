import logging
from copy import deepcopy

from infrastructure.config.base_config import CURRENT_VERSION


def _migrate_v1_to_v2(data: dict) -> dict:
    if "scrape" in data:
        data["fetch"] = data.pop("scrape")
    data["version"] = 2
    return data


class ConfigMigrator:
    def __init__(self):
        self._log = logging.getLogger(__name__)
        self.migrations = {
            1: _migrate_v1_to_v2,
        }

    def migrate(self, data: dict) -> tuple[dict, bool]:
        if data.get("version") == CURRENT_VERSION:
            return data, False

        migrated_data = deepcopy(data)
        if "version" not in migrated_data:
            self._log.info("No config version found, assuming version 1.")
            version = 1
        else:
            version = migrated_data["version"]

        was_migrated = False
        while version in self.migrations:
            self._log.info(f"Migrating config from version {version} to {version + 1}.")
            migrated_data = self.migrations[version](migrated_data)
            version = migrated_data["version"]
            was_migrated = True

        if was_migrated:
            self._log.info(f"Config migrated to version {version}")

        return migrated_data, was_migrated
