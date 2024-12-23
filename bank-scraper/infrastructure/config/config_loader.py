import yaml
from cachetools import TTLCache, cached

from application.ports.config_port import ConfigPort


class ConfigLoader(ConfigPort):
    DEFAULT_CONFIG_PATH = "resources/template_config.yml"

    def __init__(self, path: str) -> None:
        self.config_file = path

    @cached(cache=TTLCache(maxsize=1, ttl=30))
    def load(self) -> dict:
        with open(self.config_file, "r") as file:
            return yaml.safe_load(file)

    def check_or_create_default_config(self):
        try:
            self.load()
        except FileNotFoundError:
            print(f"Config file not found, creating default config at {self.config_file}")
            with open(self.DEFAULT_CONFIG_PATH, "r") as file:
                with open(self.config_file, "w") as new_file:
                    new_file.write(file.read())

        except Exception as e:
            print(f"Error loading config file: {e}")
            exit(1)

        self.load()
        print(f"Config file loaded from {self.config_file}")
