import logging
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from pathlib import Path

import strictyaml

from application.ports.config_port import ConfigPort
from application.ports.datasource_backup_port import Backupable
from domain.exception.exceptions import NoUserLogged
from domain.settings import Settings
from domain.user import User
from infrastructure.config.base_config import BASE_CONFIG, CURRENT_VERSION
from infrastructure.config.config_migrator import ConfigMigrator

CONFIG_NAME = "config.yml"


class ConfigLoader(ConfigPort, Backupable):
    def __init__(self) -> None:
        self._config_file = None
        self._log = logging.getLogger(__name__)
        self._migrator = ConfigMigrator()
        self._cache: Settings | None = None

    async def disconnect(self):
        self._log.debug("Disconnecting config loader")
        self._config_file = None
        self._cache = None

    async def connect(self, user: User):
        self._log.debug("Connecting config loader")
        self._config_file = str(user.path / CONFIG_NAME)
        await self._check_or_create_default_config()
        await self.load()

    def _check_connected(self):
        if not self._config_file:
            self._log.error("No user is currently logged in")
            raise NoUserLogged()

    async def load(self) -> Settings:
        self._check_connected()
        if self._cache is not None:
            return self._cache

        with open(self._config_file, "r") as file:
            data = strictyaml.load(file.read()).data
            settings = Settings(**data)
            self._cache = settings
            return settings

    async def raw_load(self) -> dict:
        self._check_connected()
        with open(self._config_file, "r") as file:
            return strictyaml.load(file.read()).data

    async def save(self, new_config: Settings):
        self._check_connected()
        new_config.lastUpdate = datetime.now().astimezone().isoformat()

        config_as_dict = asdict(
            new_config,
            dict_factory=lambda x: {
                k: v for (k, v) in x if (v is not None and v != {} and v != [])
            },
        )
        config_as_dict = self._to_yaml_safe(config_as_dict)
        config_as_dict["version"] = CURRENT_VERSION
        new_yaml = strictyaml.as_document(config_as_dict).as_yaml()
        with open(self._config_file, "w") as file:
            file.write(new_yaml)
        self._log.debug(f"Config file updated at {self._config_file}")

        self._cache = new_config

    async def _check_or_create_default_config(self):
        if not Path(self._config_file).is_file():
            self._log.warning(
                f"Config file not found, creating default config at {self._config_file}"
            )
            await self.save(BASE_CONFIG)

        data = await self.raw_load()

        migrated_data, was_migrated = self._migrator.migrate(data)
        settings = Settings(**migrated_data)
        if was_migrated:
            await self.save(settings)

        self._log.debug(f"Config file loaded from {self._config_file}")

    async def export(self) -> bytes:
        self._check_connected()
        current_config = await self.load()
        await self.save(current_config)

        with open(self._config_file, "rb") as file:
            return file.read()

    async def import_data(self, data: bytes):
        self._check_connected()
        with open(self._config_file, "wb") as file:
            file.write(data)

        self._log.debug(f"Config file imported to {self._config_file}")

        self._cache = None

    async def get_last_updated(self) -> datetime:
        data = await self.load()
        return datetime.fromisoformat(data.lastUpdate)

    @staticmethod
    def _to_yaml_safe(value):
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, list):
            return [ConfigLoader._to_yaml_safe(item) for item in value]
        if isinstance(value, dict):
            return {key: ConfigLoader._to_yaml_safe(val) for key, val in value.items()}
        return value
