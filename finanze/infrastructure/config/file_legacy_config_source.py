import logging
from pathlib import Path
from typing import Optional

import strictyaml

from domain.user import User
from infrastructure.config.legacy_config_source import LegacyConfigSource

CONFIG_NAME = "config.yml"


class FileLegacyConfigSource(LegacyConfigSource):
    def __init__(self):
        self._config_file: Optional[Path] = None
        self._log = logging.getLogger(__name__)

    async def connect(self, user: User):
        self._config_file = user.path / CONFIG_NAME

    async def disconnect(self):
        self._config_file = None

    async def load(self) -> Optional[dict]:
        if self._config_file is None or not self._config_file.is_file():
            return None

        try:
            data = strictyaml.load(self._config_file.read_text()).data
        except Exception as e:
            self._log.warning(f"Could not read legacy config {self._config_file}: {e}")
            return None

        return data if isinstance(data, dict) else None
