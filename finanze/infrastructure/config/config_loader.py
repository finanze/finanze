import logging
from dataclasses import asdict
from pathlib import Path

import strictyaml
from application.ports.config_port import ConfigPort
from cachetools import TTLCache, cached
from cachetools.keys import hashkey
from domain.settings import Settings
from domain.user import User
from infrastructure.config.base_config import BASE_CONFIG, CURRENT_VERSION
from infrastructure.config.config_migrator import ConfigMigrator

CONFIG_NAME = "config.yml"


class ConfigLoader(ConfigPort):
    def __init__(self) -> None:
        self._config_file = None
        self._log = logging.getLogger(__name__)
        self._migrator = ConfigMigrator()

    def disconnect(self):
        self._config_file = None
        if hasattr(self.load, "cache") and hashkey(self) in self.load.cache:
            del self.load.cache[hashkey(self)]

    def connect(self, user: User):
        self._config_file = str(user.path / CONFIG_NAME)
        self.check_or_create_default_config()

    @cached(cache=TTLCache(maxsize=1, ttl=30))
    def load(self) -> Settings:
        with open(self._config_file, "r") as file:
            data = strictyaml.load(file.read()).data
            migrated_data, was_migrated = self._migrator.migrate(data)
            settings = Settings(**migrated_data)
            if was_migrated:
                self.save(settings)
            return settings

    def save(self, new_config: Settings):
        config_as_dict = asdict(
            new_config,
            dict_factory=lambda x: {
                k: v for (k, v) in x if (v is not None and v != {} and v != [])
            },
        )
        config_as_dict["version"] = CURRENT_VERSION
        new_yaml = strictyaml.as_document(config_as_dict).as_yaml()
        with open(self._config_file, "w") as file:
            file.write(new_yaml)
        self._log.debug(f"Config file updated at {self._config_file}")

        key = hashkey(self)
        if hasattr(self.load, "cache"):
            self.load.cache[key] = new_config
        else:
            self.load.cache_clear()

    def check_or_create_default_config(self):
        if not Path(self._config_file).is_file():
            self._log.warning(
                f"Config file not found, creating default config at {self._config_file}"
            )
            self.save(BASE_CONFIG)
        self.load()
        self._log.debug(f"Config file loaded from {self._config_file}")
