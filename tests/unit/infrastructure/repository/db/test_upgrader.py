import sqlite3

import pytest

from domain.data_init import DatasourceInitContext, MigrationAheadOfTime, MigrationError
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.upgrader import (
    DBVersionMigration,
    DatabaseUpgrader,
    DuplicateMigrationNameError,
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


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sys_config (key TEXT PRIMARY KEY, value TEXT)"
    )
    conn.commit()
    yield DBClient(connection=conn), conn
    conn.close()


def _make_context():
    return DatasourceInitContext(config=None)


async def _insert_migration_record(conn, version, name):
    conn.execute(
        "INSERT INTO migrations (version, applied_at, name) VALUES (?, ?, ?)",
        (version, "2025-01-01T00:00:00", name),
    )
    conn.commit()


class _FailingCursor:
    def __init__(self, cursor, fragment, error):
        self._cursor = cursor
        self._fragment = fragment
        self._error = error

    def execute(self, statement, *args):
        if self._fragment in statement:
            raise self._error
        return self._cursor.execute(statement, *args)

    def __iter__(self):
        return iter(self._cursor)

    def __next__(self):
        return next(self._cursor)

    def __getattr__(self, item):
        return getattr(self._cursor, item)


class _FailingConnection:
    def __init__(self, connection, fragment, error):
        self._connection = connection
        self._fragment = fragment
        self._error = error

    def cursor(self):
        return _FailingCursor(self._connection.cursor(), self._fragment, self._error)

    def __getattr__(self, item):
        return getattr(self._connection, item)


def _failing_client(conn, fragment, error):
    return DBClient(connection=_FailingConnection(conn, fragment, error))


class TestUpgradeEmptyVersions:
    @pytest.mark.asyncio
    async def test_no_op_with_empty_list(self, db):
        db_client, _ = db
        upgrader = DatabaseUpgrader(db_client, [], _make_context())
        await upgrader.upgrade()


class TestUpgradeAppliesAllMigrations:
    @pytest.mark.asyncio
    async def test_applies_all_from_scratch(self, db):
        db_client, conn = db
        m0 = FakeMigration("create_users")
        m1 = FakeMigration("create_accounts")
        m2 = FakeMigration("add_indexes")
        upgrader = DatabaseUpgrader(db_client, [m0, m1, m2], _make_context())

        await upgrader.upgrade()

        assert m0.applied is True
        assert m1.applied is True
        assert m2.applied is True

        rows = conn.execute("SELECT name FROM migrations ORDER BY version").fetchall()
        assert len(rows) == 3
        assert rows[0][0] == "create_users"
        assert rows[1][0] == "create_accounts"
        assert rows[2][0] == "add_indexes"


class TestUpgradeNoOp:
    @pytest.mark.asyncio
    async def test_no_op_when_all_applied(self, db):
        db_client, conn = db
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


class TestMigrationErrorOnFailure:
    @pytest.mark.asyncio
    async def test_raises_migration_error(self, db):
        db_client, _ = db
        m0 = FakeMigration("first")
        m1 = FailingMigration("second", RuntimeError("table already exists"))
        upgrader = DatabaseUpgrader(db_client, [m0, m1], _make_context())

        with pytest.raises(MigrationError, match="second"):
            await upgrader.upgrade()

    @pytest.mark.asyncio
    async def test_successful_migrations_before_failure_are_recorded(self, db):
        db_client, conn = db
        m0 = FakeMigration("first")
        m1 = FailingMigration("second", RuntimeError("boom"))
        upgrader = DatabaseUpgrader(db_client, [m0, m1], _make_context())

        with pytest.raises(MigrationError):
            await upgrader.upgrade()

        assert m0.applied is True
        rows = conn.execute("SELECT name FROM migrations").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "first"


class TestDuplicateMigrationNameError:
    def test_raises_on_duplicate_names(self, db):
        db_client, _ = db
        m0 = FakeMigration("same_name")
        m1 = FakeMigration("same_name")

        with pytest.raises(DuplicateMigrationNameError, match="same_name"):
            DatabaseUpgrader(db_client, [m0, m1], _make_context())


class TestMigrationErrorIsDiagnosable:
    @pytest.mark.asyncio
    async def test_message_names_migration_and_keeps_cause(self, db):
        db_client, _ = db
        cause = RuntimeError("no such column: foo")
        upgrader = DatabaseUpgrader(
            db_client, [FailingMigration("add_foo", cause)], _make_context()
        )

        with pytest.raises(MigrationError) as excinfo:
            await upgrader.upgrade()

        assert "add_foo" in str(excinfo.value)
        assert "no such column: foo" in str(excinfo.value)
        assert excinfo.value.__cause__ is cause

    @pytest.mark.asyncio
    async def test_record_insert_failure_names_migration(self, db):
        _, conn = db
        db_client = _failing_client(
            conn, "INSERT INTO migrations", sqlite3.OperationalError("disk I/O error")
        )
        upgrader = DatabaseUpgrader(
            db_client, [FakeMigration("drops_table")], _make_context()
        )

        with pytest.raises(MigrationError) as excinfo:
            await upgrader.upgrade()

        assert "drops_table" in str(excinfo.value)
        assert "disk I/O error" in str(excinfo.value)
        assert excinfo.value.__cause__ is not None

    @pytest.mark.asyncio
    async def test_migrations_table_failure_is_identified(self, db):
        _, conn = db
        db_client = _failing_client(
            conn,
            "CREATE TABLE IF NOT EXISTS migrations",
            sqlite3.OperationalError("database is locked"),
        )
        upgrader = DatabaseUpgrader(db_client, [FakeMigration("any")], _make_context())

        with pytest.raises(MigrationError) as excinfo:
            await upgrader.upgrade()

        assert "migrations table" in str(excinfo.value)
        assert "database is locked" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_ahead_of_time_is_not_wrapped(self, db):
        db_client, conn = db
        conn.execute(
            "CREATE TABLE migrations (version INTEGER PRIMARY KEY, applied_at TIMESTAMP NOT NULL, name TEXT NOT NULL)"
        )
        conn.commit()
        await _insert_migration_record(conn, 0, "from_the_future")

        upgrader = DatabaseUpgrader(
            db_client, [FakeMigration("known")], _make_context()
        )

        with pytest.raises(MigrationAheadOfTime, match="from_the_future"):
            await upgrader.upgrade()


class TestUpgradeAppliesOnlyPendingMigrations:
    @pytest.mark.asyncio
    async def test_skips_already_applied(self, db):
        db_client, conn = db
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

        rows = conn.execute("SELECT name FROM migrations ORDER BY version").fetchall()
        assert len(rows) == 3

    @pytest.mark.asyncio
    async def test_applies_single_pending_migration(self, db):
        db_client, conn = db
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


class TestOutOfOrderMigrations:
    @pytest.mark.asyncio
    async def test_applies_unapplied_migration_even_if_later_ones_exist(self, db):
        db_client, conn = db
        conn.execute(
            "CREATE TABLE migrations (version INTEGER PRIMARY KEY, applied_at TIMESTAMP NOT NULL, name TEXT NOT NULL)"
        )
        conn.commit()
        await _insert_migration_record(conn, 0, "bbb")

        m0 = FakeMigration("aaa")
        m1 = FakeMigration("bbb")
        upgrader = DatabaseUpgrader(db_client, [m0, m1], _make_context())

        await upgrader.upgrade()

        assert m0.applied is True
        assert m1.applied is False

        rows = conn.execute("SELECT name FROM migrations ORDER BY version").fetchall()
        assert len(rows) == 2
        names = {r[0] for r in rows}
        assert names == {"aaa", "bbb"}

    @pytest.mark.asyncio
    async def test_applies_gap_migration_from_another_developer(self, db):
        db_client, conn = db
        conn.execute(
            "CREATE TABLE migrations (version INTEGER PRIMARY KEY, applied_at TIMESTAMP NOT NULL, name TEXT NOT NULL)"
        )
        conn.commit()
        await _insert_migration_record(conn, 0, "first")
        await _insert_migration_record(conn, 1, "third")

        m0 = FakeMigration("first")
        m1 = FakeMigration("second")
        m2 = FakeMigration("third")
        upgrader = DatabaseUpgrader(db_client, [m0, m1, m2], _make_context())

        await upgrader.upgrade()

        assert m0.applied is False
        assert m1.applied is True
        assert m2.applied is False

        rows = conn.execute("SELECT name FROM migrations").fetchall()
        assert len(rows) == 3
        names = {r[0] for r in rows}
        assert names == {"first", "second", "third"}


class TestMigrationAheadOfTime:
    @pytest.mark.asyncio
    async def test_raises_when_db_has_unknown_migrations(self, db):
        db_client, conn = db
        conn.execute(
            "CREATE TABLE migrations (version INTEGER PRIMARY KEY, applied_at TIMESTAMP NOT NULL, name TEXT NOT NULL)"
        )
        conn.commit()
        await _insert_migration_record(conn, 0, "from_another_branch")

        m0 = FakeMigration("my_migration")
        upgrader = DatabaseUpgrader(db_client, [m0], _make_context())

        with pytest.raises(MigrationAheadOfTime, match="from_another_branch"):
            await upgrader.upgrade()
