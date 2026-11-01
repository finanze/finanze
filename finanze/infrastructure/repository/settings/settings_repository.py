import logging
from datetime import datetime
from typing import Any, Optional
from warnings import deprecated

from application.ports.config_port import ConfigPort
from domain.settings import PartialSettings, Settings, SettingsSection
from domain.user import User
from infrastructure.config.base_config import BASE_CONFIG
from infrastructure.config.legacy_config_source import LegacyConfigSource
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.settings.queries import SettingsQueries
from infrastructure.repository.settings.settings_mapper import (
    deserialize_section,
    parse_timestamp,
    sections_to_partial_settings,
    sections_to_settings,
    serialize_section,
    settings_to_sections,
)


class SettingsRepository(ConfigPort):
    def __init__(self, client: DBClient, legacy_source: LegacyConfigSource):
        self._db_client = client
        self._legacy_source = legacy_source
        self._log = logging.getLogger(__name__)

    async def connect(self, user: User):
        await self._legacy_source.connect(user)

    async def disconnect(self):
        await self._legacy_source.disconnect()

    async def _get_rows(
        self, keys: Optional[list[str]] = None
    ) -> dict[str, tuple[str, str]]:
        async with self._db_client.read() as cursor:
            if keys is None:
                await cursor.execute(SettingsQueries.GET_ALL)
            else:
                await cursor.execute(SettingsQueries.get_by_keys(len(keys)), keys)
            rows = await cursor.fetchall()
            return {row["key"]: (row["value"], row["updated_at"]) for row in rows}

    @staticmethod
    def _last_update(rows: dict[str, tuple[str, str]]) -> Optional[datetime]:
        timestamps = [parse_timestamp(updated_at) for _, updated_at in rows.values()]
        timestamps = [ts for ts in timestamps if ts is not None]
        return max(timestamps) if timestamps else None

    def _last_update_value(self, rows: dict[str, tuple[str, str]]) -> str:
        last_update = self._last_update(rows)
        return last_update.isoformat() if last_update else BASE_CONFIG.lastUpdate

    def _deserialize_rows(self, rows: dict[str, tuple[str, str]]) -> dict[str, Any]:
        sections = {}
        for key, (value, _) in rows.items():
            try:
                sections[key] = deserialize_section(value)
            except Exception as e:
                self._log.warning(f"Invalid stored settings section '{key}': {e}")
        return sections

    async def load(self) -> Settings:
        rows = await self._get_rows()
        return sections_to_settings(
            self._deserialize_rows(rows), self._last_update_value(rows)
        )

    async def load_sections(self, sections: set[SettingsSection]) -> PartialSettings:
        keys = [section.value for section in SettingsSection if section in sections]
        rows = await self._get_rows(keys) if keys else {}
        return sections_to_partial_settings(
            self._deserialize_rows(rows), keys, self._last_update_value(rows)
        )

    async def save(self, new_config: Settings | PartialSettings):
        sections = settings_to_sections(new_config)
        if not sections:
            return

        rows = await self._get_rows(list(sections))

        changed = {}
        for key, section in sections.items():
            stored = rows.get(key)
            if stored is not None:
                try:
                    if deserialize_section(stored[0]) == section:
                        continue
                except Exception:
                    pass
            changed[key] = section

        if not changed:
            return

        updated_at = datetime.now().astimezone().isoformat()
        async with self._db_client.tx() as cursor:
            for key, section in changed.items():
                await cursor.execute(
                    SettingsQueries.UPSERT,
                    (key, serialize_section(section), updated_at),
                )

    @deprecated(
        "Only for database upgrades that import pre-database config storage.",
        category=None,
    )
    async def load_legacy(self) -> Optional[dict]:
        try:
            return await self._legacy_source.load()
        except Exception as e:
            self._log.warning(f"Could not load legacy config: {e}")
            return None

    @deprecated(
        "Only for importing or migrating legacy config; use save() for current settings.",
        category=None,
    )
    async def apply_legacy(
        self, sections: dict[str, dict], last_update: Optional[datetime]
    ) -> bool:
        if not sections:
            return False

        rows = await self._get_rows()
        if rows:
            current_last_update = self._last_update(rows)
            if last_update is None or (
                current_last_update is not None and last_update <= current_last_update
            ):
                return False

        updated_at = (last_update or datetime.now().astimezone()).isoformat()
        async with self._db_client.tx() as cursor:
            await cursor.execute(SettingsQueries.DELETE_ALL)
            for key, section in sections.items():
                await cursor.execute(
                    SettingsQueries.UPSERT,
                    (key, serialize_section(section), updated_at),
                )
        return True
