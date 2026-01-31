import json
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from typing import Optional
from js import jsBridge

from application.ports.config_port import ConfigPort
from application.ports.datasource_backup_port import Backupable
from domain.settings import CURRENT_VERSION, Settings
from infrastructure.config.base_config import BASE_CONFIG
from infrastructure.config.config_migrator import ConfigMigrator


class CapacitorConfigAdapter(ConfigPort, Backupable):
    def __init__(self):
        self._cache: Optional[Settings] = None
        self._prefs_key: Optional[str] = None
        self._migrator = ConfigMigrator()

    def set_cache(self, settings: Settings):
        self._cache = settings

    @staticmethod
    def _default_settings() -> Settings:
        cfg = deepcopy(BASE_CONFIG)
        cfg.lastUpdate = datetime.now().astimezone().isoformat()
        return cfg

    @staticmethod
    def _to_json_safe(value):
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, list):
            return [CapacitorConfigAdapter._to_json_safe(v) for v in value]
        if isinstance(value, dict):
            return {
                k: CapacitorConfigAdapter._to_json_safe(v) for k, v in value.items()
            }
        return value

    @staticmethod
    def _to_yaml_safe(value):
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, list):
            return [CapacitorConfigAdapter._to_yaml_safe(v) for v in value]
        if isinstance(value, dict):
            return {
                k: CapacitorConfigAdapter._to_yaml_safe(v) for k, v in value.items()
            }
        return value

    @staticmethod
    def _settings_as_dict(settings: Settings) -> dict:
        return asdict(
            settings,
            dict_factory=lambda items: {
                k: v for (k, v) in items if (v is not None and v != {} and v != [])
            },
        )

    async def _persist(self, settings: Settings, *, touch_last_update: bool) -> None:
        if touch_last_update or not getattr(settings, "lastUpdate", None):
            settings.lastUpdate = datetime.now().astimezone().isoformat()

        settings.version = CURRENT_VERSION

        self._cache = settings

        try:
            payload = self._to_json_safe(self._settings_as_dict(settings))
            json_str = json.dumps(payload)
        except Exception:
            json_str = "{}"

        await jsBridge.preferences.set(self._prefs_key, json_str)

    async def connect(self, user):
        self._prefs_key = f"config:{user.hashed_id()}"
        await self.load()

    async def disconnect(self):
        self._cache = None
        self._prefs_key = None

    async def load(self) -> Settings:
        if self._cache is not None:
            return self._cache

        if self._prefs_key is None:
            self._cache = self._default_settings()
            return self._cache

        val = await jsBridge.preferences.get(self._prefs_key)
        if not val:
            self._cache = self._default_settings()
            await self.save(self._cache)
            return self._cache

        try:
            data = json.loads(val)
            if isinstance(data, dict):
                self._cache = Settings(**data)
            else:
                self._cache = self._default_settings()
        except Exception:
            self._cache = self._default_settings()

        return self._cache

    async def raw_load(self) -> dict:
        settings = await self.load()
        try:
            return asdict(settings)
        except Exception:
            return {}

    async def save(self, new_config: Settings) -> None:
        await self._persist(new_config, touch_last_update=True)

    async def export(self) -> bytes:
        import strictyaml

        from infrastructure.cloud.backup.capacitor_backup_processor import (
            write_staging_file,
        )

        current_config = await self.load()
        await self._persist(current_config, touch_last_update=True)

        payload = self._to_yaml_safe(self._settings_as_dict(current_config))
        payload["version"] = CURRENT_VERSION
        yaml_bytes = strictyaml.as_document(payload).as_yaml().encode("utf-8")

        await write_staging_file("EXPORTED_CONFIG", yaml_bytes)
        return b""

    async def import_data(self, data: bytes) -> None:
        import strictyaml

        from infrastructure.cloud.backup.capacitor_backup_processor import (
            read_staging_file,
            delete_staging_file,
        )

        raw_bytes = await read_staging_file("DECOMPILED_CONFIG")
        await delete_staging_file("DECOMPILED_CONFIG")
        raw = raw_bytes.decode("utf-8")

        parsed = strictyaml.load(raw).data

        if not isinstance(parsed, dict):
            raise ValueError("Invalid config backup payload")

        migrated_data, _ = self._migrator.migrate(parsed)
        settings = Settings(**migrated_data)

        self._cache = settings
        payload = self._to_json_safe(self._settings_as_dict(settings))
        await jsBridge.preferences.set(self._prefs_key, json.dumps(payload))

    async def get_last_updated(self) -> datetime:
        settings = await self.load()
        return datetime.fromisoformat(settings.lastUpdate)
