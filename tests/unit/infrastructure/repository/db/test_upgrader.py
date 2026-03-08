import sqlite3

import pytest

from domain.data_init import DatasourceInitContext, MigrationAheadOfTime, MigrationError
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.upgrader import (
    DBVersionMigration,
    DatabaseUpgrader,
    MigrationIntegrityError,
)


class FakeMigration(DBVersionMigration):
    def __init__(self, migration_name, callback=None):
        self._name = migration_name
        self._callback = callback
        self.applied = False
        self.applied_count = 0

    @property
    def name(self):
        return self._name

    async def upgrade(self, cursor, context):
        self.applied = True
        self.applied_count += 1
        if self._callback:
            await self._callback(cursor, context)


class FailingMigration(DBVersionMigration):
    def __init__(self, migration_name, error):
        self._name = migration_name
        self._error = error

    @property
    def name(self):
        return self._name

    async def upgrade(self, cursor, context):
        raise self._error


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sys_config (key TEXT PRIMARY KEY, value TEXT)"
    )
    conn.commit()
    return DBClient(connection=conn), conn


def _make_context():
    return DatasourceInitContext(config=None)


async def _insert_migration_record(conn, version, name):
    conn.execute(
        "INSERT INTO migrations (version, applied_at, name) VALUES (?, ?, ?)",
        (version, "2025-01-01T00:00:00", name),
    )
    conn.commit()


class TestUpgradeEmptyVersions:
    @pytest.mark.asyncio
    async def test_raises_value_error(self):
        db_client, _ = _make_db()
        upgrader = DatabaseUpgrader(db_client, [], _make_context())

        with pytest.raises(ValueError, match="Invalid target version"):
            await upgrader.upgrade()


class TestUpgradeAppliesAllMigrations:
    @pytest.mark.asyncio
    async def test_applies_all_from_scratch(self):
        db_client, conn = _make_db()
        m0 = FakeMigration("create_users")
        m1 = FakeMigration("create_accounts")
        m2 = FakeMigration("add_indexes")
        upgrader = DatabaseUpgrader(db_client, [m0, m1, m2], _make_context())

        await upgrader.upgrade()

        assert m0.applied is True
        assert m1.applied is True
        assert m2.applied is True

        rows = conn.execute(
            "SELECT version, name FROM migrations ORDER BY version"
        ).fetchall()
        assert len(rows) == 3
        assert rows[0] == (0, "create_users")
        assert rows[1] == (1, "create_accounts")
        assert rows[2] == (2, "add_indexes")

    @pytest.mark.asyncio
    async def test_applies_up_to_explicit_target(self):
        db_client, conn = _make_db()
        m0 = FakeMigration("first")
        m1 = FakeMigration("second")
        m2 = FakeMigration("third")
        upgrader = DatabaseUpgrader(db_client, [m0, m1, m2], _make_context())

        await upgrader.upgrade(target_version=1)

        assert m0.applied is True
        assert m1.applied is True
        assert m2.applied is False

        rows = conn.execute(
            "SELECT version FROM migrations ORDER BY version"
        ).fetchall()
        assert [r[0] for r in rows] == [0, 1]


class TestUpgradeNoOp:
    @pytest.mark.asyncio
    async def test_no_op_when_already_at_target(self):
        db_client, conn = _make_db()
        conn.execute(
            "CREATE TABLE migrations (version INTEGER PRIMARY KEY, applied_at TIMESTAMP NOT NULL, name TEXT NOT NULL)"
        )
        conn.commit()
        await _insert_migration_record(conn, 0, "first")
        await _insert_migration_record(conn, 1, "second")

        m0 = FakeMigration("first")
        m1 = FakeMigration("second")
        upgrader = DatabaseUpgrader(db_client, [m0, m1], _make_context())

        await upgrader.upgrade()

        assert m0.applied is False
        assert m1.applied is False


class TestMigrationAheadOfTimeError:
    @pytest.mark.asyncio
    async def test_raises_when_current_ahead_of_target(self):
        db_client, conn = _make_db()
        conn.execute(
            "CREATE TABLE migrations (version INTEGER PRIMARY KEY, applied_at TIMESTAMP NOT NULL, name TEXT NOT NULL)"
        )
        conn.commit()
        await _insert_migration_record(conn, 0, "first")
        await _insert_migration_record(conn, 1, "second")
        await _insert_migration_record(conn, 2, "third")

        m0 = FakeMigration("first")
        m1 = FakeMigration("second")
        m2 = FakeMigration("third")
        upgrader = DatabaseUpgrader(db_client, [m0, m1, m2], _make_context())

        with pytest.raises(MigrationAheadOfTime, match="ahead of current one"):
            await upgrader.upgrade(target_version=1)


class TestMigrationErrorOnFailure:
    @pytest.mark.asyncio
    async def test_raises_migration_error(self):
        db_client, _ = _make_db()
        m0 = FakeMigration("first")
        m1 = FailingMigration("second", RuntimeError("table already exists"))
        upgrader = DatabaseUpgrader(db_client, [m0, m1], _make_context())

        with pytest.raises(MigrationError, match="second"):
            await upgrader.upgrade()

    @pytest.mark.asyncio
    async def test_successful_migrations_before_failure_are_recorded(self):
        db_client, conn = _make_db()
        m0 = FakeMigration("first")
        m1 = FailingMigration("second", RuntimeError("boom"))
        upgrader = DatabaseUpgrader(db_client, [m0, m1], _make_context())

        with pytest.raises(MigrationError):
            await upgrader.upgrade()

        assert m0.applied is True
        rows = conn.execute("SELECT version, name FROM migrations").fetchall()
        assert len(rows) == 1
        assert rows[0] == (0, "first")


class TestMigrationIntegrityErrorOnNameMismatch:
    @pytest.mark.asyncio
    async def test_raises_on_name_mismatch(self):
        db_client, conn = _make_db()
        conn.execute(
            "CREATE TABLE migrations (version INTEGER PRIMARY KEY, applied_at TIMESTAMP NOT NULL, name TEXT NOT NULL)"
        )
        conn.commit()
        await _insert_migration_record(conn, 0, "old_name")

        m0 = FakeMigration("new_name")
        m1 = FakeMigration("second")
        upgrader = DatabaseUpgrader(db_client, [m0, m1], _make_context())

        with pytest.raises(MigrationIntegrityError, match="Name mismatch"):
            await upgrader.upgrade()

    @pytest.mark.asyncio
    async def test_raises_on_name_mismatch_for_earlier_migration(self):
        db_client, conn = _make_db()
        conn.execute(
            "CREATE TABLE migrations (version INTEGER PRIMARY KEY, applied_at TIMESTAMP NOT NULL, name TEXT NOT NULL)"
        )
        conn.commit()
        await _insert_migration_record(conn, 0, "wrong_name")
        await _insert_migration_record(conn, 1, "second")

        m0 = FakeMigration("first")
        m1 = FakeMigration("second")
        m2 = FakeMigration("third")
        upgrader = DatabaseUpgrader(db_client, [m0, m1, m2], _make_context())

        with pytest.raises(MigrationIntegrityError, match="Name mismatch"):
            await upgrader.upgrade()


class TestUpgradeAppliesOnlyPendingMigrations:
    @pytest.mark.asyncio
    async def test_skips_already_applied(self):
        db_client, conn = _make_db()
        conn.execute(
            "CREATE TABLE migrations (version INTEGER PRIMARY KEY, applied_at TIMESTAMP NOT NULL, name TEXT NOT NULL)"
        )
        conn.commit()
        await _insert_migration_record(conn, 0, "first")

        m0 = FakeMigration("first")
        m1 = FakeMigration("second")
        m2 = FakeMigration("third")
        upgrader = DatabaseUpgrader(db_client, [m0, m1, m2], _make_context())

        await upgrader.upgrade()

        assert m0.applied is False
        assert m1.applied is True
        assert m2.applied is True

        rows = conn.execute(
            "SELECT version, name FROM migrations ORDER BY version"
        ).fetchall()
        assert len(rows) == 3
        assert rows[0] == (0, "first")
        assert rows[1] == (1, "second")
        assert rows[2] == (2, "third")

    @pytest.mark.asyncio
    async def test_applies_single_pending_migration(self):
        db_client, conn = _make_db()
        conn.execute(
            "CREATE TABLE migrations (version INTEGER PRIMARY KEY, applied_at TIMESTAMP NOT NULL, name TEXT NOT NULL)"
        )
        conn.commit()
        await _insert_migration_record(conn, 0, "first")
        await _insert_migration_record(conn, 1, "second")

        m0 = FakeMigration("first")
        m1 = FakeMigration("second")
        m2 = FakeMigration("third")
        upgrader = DatabaseUpgrader(db_client, [m0, m1, m2], _make_context())

        await upgrader.upgrade()

        assert m0.applied is False
        assert m1.applied is False
        assert m2.applied is True
        assert m2.applied_count == 1
