import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Set

from domain.data_init import DatasourceInitContext, MigrationAheadOfTime, MigrationError
from infrastructure.repository.db.client import DBClient, DBCursor


class DuplicateMigrationNameError(Exception):
    pass


class DBVersionMigration(ABC):
    @property
    @abstractmethod
    def name(self):
        pass

    @abstractmethod
    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        pass


class DatabaseUpgrader:
    def __init__(
        self,
        db_client: DBClient,
        versions: List[DBVersionMigration],
        context: DatasourceInitContext,
    ):
        self._db_client = db_client
        self._versions = versions
        self._context = context
        self._log = logging.getLogger(__name__)
        self._validate_no_duplicate_names()

    def _validate_no_duplicate_names(self):
        seen = set()
        for v in self._versions:
            if v.name in seen:
                raise DuplicateMigrationNameError(f"Duplicate migration name: {v.name}")
            seen.add(v.name)

    async def _ensure_migrations_table(self):
        async with self._db_client.tx(skip_last_update=True) as cursor:
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS migrations
                (
                    version    INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP NOT NULL,
                    name       TEXT      NOT NULL
                )
                """
            )

    async def _get_applied_migration_names(self) -> Set[str]:
        async with self._db_client.read() as cursor:
            await cursor.execute("SELECT name FROM migrations")
            rows = await cursor.fetchall()
            return {row[0] for row in rows}

    async def _get_next_version(self) -> int:
        async with self._db_client.read() as cursor:
            await cursor.execute("SELECT MAX(version) FROM migrations")
            result = await cursor.fetchone()
            return (result[0] + 1) if result[0] is not None else 0

    async def upgrade(self):
        if not self._versions:
            return

        await self._ensure_migrations_table()

        applied_names = await self._get_applied_migration_names()
        known_names = {m.name for m in self._versions}
        unknown_applied = applied_names - known_names
        if unknown_applied:
            raise MigrationAheadOfTime(
                f"Database has migrations not present in this version: {', '.join(sorted(unknown_applied))}"
            )

        pending = [m for m in self._versions if m.name not in applied_names]

        if not pending:
            self._log.debug("No pending migrations to apply.")
            return

        next_version = await self._get_next_version()

        for migration in pending:
            async with self._db_client.tx(skip_last_update=True) as cursor:
                self._log.info(f"Applying migration: {migration.name}")
                try:
                    await migration.upgrade(cursor, self._context)
                except Exception as e:
                    raise MigrationError(
                        f"There was an error while executing migration {migration.name}: {str(e)}"
                    ) from e

                applied_at = datetime.now().astimezone().isoformat()

                await cursor.execute(
                    "INSERT INTO migrations (version, applied_at, name) VALUES (?, ?, ?)",
                    (next_version, applied_at, migration.name),
                )
                next_version += 1

        async with self._db_client.tx():
            # Update last update date after successful migration
            pass
