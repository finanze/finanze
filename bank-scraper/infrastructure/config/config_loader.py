import logging
import shutil
from pathlib import Path

import yaml
from cachetools import TTLCache, cached

from application.ports.config_port import ConfigPort


class ConfigLoader(ConfigPort):
    DEFAULT_CONFIG_PATH = "resources/template_config.yml"

    def __init__(self, path: str) -> None:
        self._config_file = path
        self._config_path = Path(path)

        self._log = logging.getLogger(__name__)

    @cached(cache=TTLCache(maxsize=1, ttl=30))
    def load(self) -> dict:
        with open(self._config_file, "r") as file:
            return yaml.safe_load(file)

    def check_or_create_default_config(self):
        if not self._config_path.is_file():
            self._log.warning(f"Config file not found, creating default config at {self._config_file}")
            shutil.copyfile(self.DEFAULT_CONFIG_PATH, self._config_file)

        self.load()
        self._log.info(f"Config file loaded from {self._config_file}")
