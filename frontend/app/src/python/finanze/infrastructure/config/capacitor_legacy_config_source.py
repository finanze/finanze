import json
import logging
from typing import Optional

from js import jsBridge

from domain.user import User
from infrastructure.config.legacy_config_source import LegacyConfigSource


class CapacitorLegacyConfigSource(LegacyConfigSource):
    def __init__(self):
        self._prefs_key: Optional[str] = None
        self._log = logging.getLogger(__name__)

    async def connect(self, user: User):
        self._prefs_key = f"config:{user.hashed_id()}"

    async def disconnect(self):
        self._prefs_key = None

    async def load(self) -> Optional[dict]:
        if self._prefs_key is None:
            return None

        try:
            value = await jsBridge.preferences.get(self._prefs_key)
            if not value:
                return None
            data = json.loads(value)
        except Exception as e:
            self._log.warning(f"Could not read legacy config preferences: {e}")
            return None

        return data if isinstance(data, dict) else None
