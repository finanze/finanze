from abc import ABC, abstractmethod
from datetime import datetime
from typing import List

from dateutil.tz import tzlocal

from infrastructure.repository.db.client import DBClient, DBCursor


class MigrationIntegrityError(Exception):
    """Raised when a migration integrity check fails."""
    pass


class DBVersionMigration(ABC):
    """
    Interface that all database version migrations must implement.
    """

    @property
    @abstractmethod
    def name(self):
        """
        A human-readable name for the migration.
        """
        pass

    @abstractmethod
    def upgrade(self, cursor: DBCursor):
        """
        Perform the database upgrade for this migration.
        """
        pass


class DatabaseUpgrader:
    """
    Handles database version upgrades using SQL transactions and tracks migration history.
    """

    def __init__(self, db_client: DBClient, versions: List[DBVersionMigration]):
        self._db_client = db_client
        self._versions = versions
        self._ensure_migrations_table()

    def _ensure_migrations_table(self):
        """
        Creates the migrations table if it doesn't exist.
        """
        with self._db_client.tx() as cursor:
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS migrations
                           (
                               version    INTEGER PRIMARY KEY,
                               applied_at TIMESTAMP NOT NULL,
                               name       TEXT      NOT NULL
                           )
                           """)

    def _get_current_version(self) -> int:
        """
        Returns the highest version number from the migrations table.
        """
        with self._db_client.read() as cursor:
            cursor.execute("SELECT MAX(version) FROM migrations")
            result = cursor.fetchone()
            return result[0] if result[0] is not None else -1

    def _validate_migrations(self):
        """
        Validates that all applied migrations match the current names.
        """
        with self._db_client.read() as cursor:
            cursor.execute("SELECT version, name FROM migrations ORDER BY version")
            applied_migrations = cursor.fetchall()

            for version, applied_name in applied_migrations:
                if version >= len(self._versions):
                    raise MigrationIntegrityError(
                        f"Migration version {version} does not exist in the provided versions"
                    )

                current_migration = self._versions[version]
                if current_migration.name != applied_name:
                    raise MigrationIntegrityError(
                        f"Name mismatch for migration version {version}. "
                        f"Applied: {applied_name}, Current: {current_migration.name}"
                    )

    def upgrade(self, target_version=None):
        """
        Upgrades the database to the specified target version.
        If target_version is None, upgrades to the latest version.
        """
        current = self._get_current_version()
        if target_version is None:
            target = len(self._versions) - 1
        else:
            target = target_version

        if target < 0 or target >= len(self._versions):
            raise ValueError(f"Invalid target version: {target}")

        if current >= target:
            return  # Already at or beyond the target

        self._validate_migrations()

        # Calculate versions to apply
        versions_to_apply = range(current + 1, target + 1)

        for version in versions_to_apply:
            with self._db_client.tx() as cursor:
                migration = self._versions[version]
                # Execute the migration
                migration.upgrade(cursor)

                applied_at = datetime.now(tzlocal())

                # Record the migration
                cursor.execute(
                    "INSERT INTO migrations (version, applied_at, name) VALUES (?, ?, ?)",
                    (version, applied_at, migration.name)
                )
