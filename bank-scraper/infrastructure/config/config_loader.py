import shutil
from pathlib import Path

import yaml
from cachetools import TTLCache, cached

from application.ports.config_port import ConfigPort


class ConfigLoader(ConfigPort):
    DEFAULT_CONFIG_PATH = "resources/template_config.yml"

    def __init__(self, path: str) -> None:
        self.config_file = path
        self.config_path = Path(path)

    @cached(cache=TTLCache(maxsize=1, ttl=30))
    def load(self) -> dict:
        with open(self.config_file, "r") as file:
            return yaml.safe_load(file)

    def check_or_create_default_config(self):
        if not self.config_path.is_file():
            print(f"Config file not found, creating default config at {self.config_file}")
            shutil.copy(self.DEFAULT_CONFIG_PATH, self.config_file)

        self.load()
        print(f"Config file loaded from {self.config_file}")
