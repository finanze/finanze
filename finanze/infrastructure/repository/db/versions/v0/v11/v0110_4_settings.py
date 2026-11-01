import logging
from datetime import datetime

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      CREATE TABLE settings
      (
          "key"      VARCHAR(32) PRIMARY KEY,
          value      TEXT        NOT NULL,
          updated_at TIMESTAMP   NOT NULL
      );
      """


class V01104Settings(DBVersionMigration, QueryMixin):
    def __init__(self):
        self._log = logging.getLogger(__name__)

    @property
    def name(self):
        return "v0.11.0:4_settings"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        for statement in self.parse_block(DDL):
            await cursor.execute(statement)

        config_port = context.config if context else None
        if config_port is None:
            return

        try:
            # Deferred import, mapper depends on non core modules (mobile tiers)
            from infrastructure.repository.settings.settings_mapper import (
                legacy_to_sections,
                serialize_section,
            )

            raw = await config_port.load_legacy()
            sections, last_update = legacy_to_sections(raw)
            updated_at = (last_update or datetime.now().astimezone()).isoformat()
            for key, section in sections.items():
                await cursor.execute(
                    'INSERT INTO settings ("key", value, updated_at) VALUES (?, ?, ?)',
                    (key, serialize_section(section), updated_at),
                )
            self._log.info("Migrated %d legacy settings sections", len(sections))
        except Exception as e:
            self._log.exception(f"Could not migrate legacy settings: {e}")
