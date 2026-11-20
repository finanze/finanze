import sqlite3
import uuid

import pytest

from domain.data_init import (
    DatasourceInitParams,
    MigrationAheadOfTime,
    MigrationError,
)
from domain.user import User
from infrastructure.repository.db import manager as manager_module
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.manager import DBManager
from infrastructure.repository.db.upgrader import DBVersionMigration
from infrastructure.repository.db.version_registry import (
    compute_schema_hash,
    get_schema_hash,
    get_schema_revision,
)


class _FailingMigration(DBVersionMigration):
    def __init__(self, migration_name="failing_migration"):
        self._name = migration_name

    @property
    def name(self):
        return self._name

    async def upgrade(self, cursor, context):
        raise RuntimeError("boom")


class _BaseSchemaMigration(DBVersionMigration):
    def __init__(self, migration_name="v0 Genesis"):
        self._name = migration_name

    @property
    def name(self):
        return self._name

    async def upgrade(self, cursor, context):
        await cursor.execute(
            "CREATE TABLE IF NOT EXISTS sys_config (key TEXT PRIMARY KEY, value TEXT)"
        )
        await cursor.execute("CREATE TABLE IF NOT EXISTS records (val TEXT NOT NULL)")


class _NoOpMigration(DBVersionMigration):
    def __init__(self, migration_name):
        self._name = migration_name

    @property
    def name(self):
        return self._name

    async def upgrade(self, cursor, context):
        pass


def _build_sqlite_payload(tmp_path, filename, migration_names, record_values=()):
    db_file = tmp_path / filename
    conn = sqlite3.connect(str(db_file))
    try:
        conn.execute("CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("CREATE TABLE records (val TEXT NOT NULL)")
        conn.execute(
            "CREATE TABLE migrations (version INTEGER PRIMARY KEY, applied_at TIMESTAMP NOT NULL, name TEXT NOT NULL)"
        )
        for idx, m_name in enumerate(migration_names):
            conn.execute(
                "INSERT INTO migrations (version, applied_at, name) VALUES (?, ?, ?)",
                (idx, "2026-01-01T00:00:00+00:00", m_name),
            )
        for val in record_values:
            conn.execute("INSERT INTO records (val) VALUES (?)", (val,))
        conn.commit()
    finally:
        conn.close()
    return db_file.read_bytes()


@pytest.fixture
def user(tmp_path):
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    return User(
        id=uuid.uuid4(),
        username="testuser",
        path=user_dir,
        last_login=None,
    )


class TestInitializeMigrationFailureLocksDatabase:
    @pytest.mark.asyncio
    async def test_stays_locked_on_migration_error(self, user, monkeypatch):
        monkeypatch.setattr(manager_module, "versions", [_FailingMigration()])
        db_manager = DBManager(DBClient())

        params = DatasourceInitParams.build(user=user, password="secret123")

        with pytest.raises(MigrationError):
            await db_manager.initialize(params)

        assert db_manager.unlocked is False
        assert db_manager._client._conn is None
        assert await db_manager.get_hashed_password() is None


class TestDBManagerImportPrecheckAndRollback:
    def test_get_version_matches_registry_schema_version(self):
        db_manager = DBManager(DBClient())
        assert db_manager.get_schema_revision() == get_schema_revision()
        assert db_manager.get_schema_hash() == get_schema_hash()
        assert len(get_schema_hash()) == 43
        assert compute_schema_hash(["M", "A", "H"]) == compute_schema_hash(
            ["H", "M", "A"]
        )
        assert compute_schema_hash(["M", "A"]) != compute_schema_hash(["M", "H"])

    @pytest.mark.asyncio
    async def test_import_ahead_of_time_keeps_existing_db_unlocked_and_intact(
        self, tmp_path, user, monkeypatch
    ):
        base_migration = _BaseSchemaMigration("v0 Genesis")
        monkeypatch.setattr(manager_module, "versions", [base_migration])

        client = DBClient()
        db_manager = DBManager(client)
        await db_manager.initialize(
            DatasourceInitParams.build(user=user, password="secret123")
        )
        async with client.tx() as cursor:
            await cursor.execute(
                "INSERT INTO records (val) VALUES (?)", ("original-data",)
            )

        future_payload = _build_sqlite_payload(
            tmp_path,
            "future_backup.db",
            ["unrecognized_migration_at_same_revision"],
            record_values=("future-data",),
        )

        with pytest.raises(
            MigrationAheadOfTime, match="unrecognized_migration_at_same_revision"
        ):
            await db_manager.import_data(future_payload, initialize=False)

        assert db_manager.unlocked is True
        assert not (user.path / "data.db.tmp").exists()
        async with client.read() as cursor:
            await cursor.execute("SELECT val FROM records")
            rows = [r[0] for r in await cursor.fetchall()]
        assert rows == ["original-data"]
        await db_manager.lock()

    @pytest.mark.asyncio
    async def test_initial_import_ahead_of_time_leaves_no_db_file(
        self, tmp_path, user, monkeypatch
    ):
        monkeypatch.setattr(
            manager_module, "versions", [_BaseSchemaMigration("v0 Genesis")]
        )
        db_manager = DBManager(DBClient())

        future_payload = _build_sqlite_payload(
            tmp_path,
            "future_init.db",
            ["v0 Genesis", "v99.0.0:0_future"],
        )

        with pytest.raises(MigrationAheadOfTime, match="v99.0.0:0_future"):
            await db_manager.import_data(
                future_payload,
                initialize=True,
                user=user,
                password="secret123",
            )

        assert db_manager.unlocked is False
        assert not (user.path / "data.db").exists()
        assert not (user.path / "data.db-wal").exists()
        assert not (user.path / "data.db-shm").exists()

    @pytest.mark.asyncio
    async def test_initial_import_migration_failure_cleans_up_db_files(
        self, tmp_path, user, monkeypatch
    ):
        monkeypatch.setattr(
            manager_module,
            "versions",
            [
                _BaseSchemaMigration("v0 Genesis"),
                _FailingMigration("v0.2.0:0_broken"),
            ],
        )
        db_manager = DBManager(DBClient())

        older_payload = _build_sqlite_payload(
            tmp_path,
            "older_init.db",
            ["v0 Genesis"],
        )

        with pytest.raises(MigrationError, match="v0.2.0:0_broken"):
            await db_manager.import_data(
                older_payload,
                initialize=True,
                user=user,
                password="secret123",
            )

        assert db_manager.unlocked is False
        assert not (user.path / "data.db").exists()

    @pytest.mark.asyncio
    async def test_import_rollback_restores_original_db_when_initialize_fails(
        self, tmp_path, user, monkeypatch
    ):
        base_migration = _BaseSchemaMigration("v0 Genesis")
        second_migration = _NoOpMigration("v0.2.0:0_step")
        monkeypatch.setattr(
            manager_module, "versions", [base_migration, second_migration]
        )

        client = DBClient()
        db_manager = DBManager(client)
        await db_manager.initialize(
            DatasourceInitParams.build(user=user, password="secret123")
        )
        async with client.tx() as cursor:
            await cursor.execute(
                "INSERT INTO records (val) VALUES (?)", ("original-data",)
            )

        monkeypatch.setattr(
            manager_module,
            "versions",
            [base_migration, _FailingMigration("v0.2.0:0_step")],
        )

        older_payload = _build_sqlite_payload(
            tmp_path,
            "older_backup.db",
            ["v0 Genesis"],
            record_values=("imported-data",),
        )

        with pytest.raises(MigrationError, match="v0.2.0:0_step"):
            await db_manager.import_data(older_payload, initialize=False)

        assert db_manager.unlocked is True
        assert (user.path / "data.db").exists()
        assert not (user.path / "data.db.tmp").exists()
        async with client.read() as cursor:
            await cursor.execute("SELECT val FROM records")
            rows = [r[0] for r in await cursor.fetchall()]
        assert rows == ["original-data"]
        await db_manager.lock()

    @pytest.mark.asyncio
    async def test_export_and_import_support_paths_with_single_quotes(
        self, tmp_path, monkeypatch
    ):
        base_migration = _BaseSchemaMigration("v0 Genesis")
        monkeypatch.setattr(manager_module, "versions", [base_migration])

        quoted_src_dir = tmp_path / "O'Connor's Data"
        quoted_src_dir.mkdir()
        src_user = User(
            id=uuid.uuid4(),
            username="oconnor",
            path=quoted_src_dir,
            last_login=None,
        )

        src_client = DBClient()
        src_manager = DBManager(src_client)
        await src_manager.initialize(
            DatasourceInitParams.build(user=src_user, password="secret'123")
        )
        async with src_client.tx() as cursor:
            await cursor.execute(
                "INSERT INTO records (val) VALUES (?)", ("quoted-path-row",)
            )
        exported_bytes = await src_manager.export()
        await src_manager.lock()

        quoted_dst_dir = tmp_path / "Dest'Dir"
        quoted_dst_dir.mkdir()
        dst_user = User(
            id=uuid.uuid4(),
            username="oconnor2",
            path=quoted_dst_dir,
            last_login=None,
        )
        dst_client = DBClient()
        dst_manager = DBManager(dst_client)
        await dst_manager.import_data(
            exported_bytes,
            initialize=True,
            user=dst_user,
            password="secret'456",
        )
        async with dst_client.read() as cursor:
            await cursor.execute("SELECT val FROM records")
            rows = [r[0] for r in await cursor.fetchall()]
        assert rows == ["quoted-path-row"]

        updated_payload = _build_sqlite_payload(
            tmp_path,
            "updated_quoted.db",
            ["v0 Genesis"],
            record_values=("updated-quoted-row",),
        )
        await dst_manager.import_data(updated_payload, initialize=False)
        async with dst_client.read() as cursor:
            await cursor.execute("SELECT val FROM records")
            rows = [r[0] for r in await cursor.fetchall()]
        assert rows == ["updated-quoted-row"]
        await dst_manager.lock()

    @pytest.mark.asyncio
    async def test_import_rollback_preserves_uncheckpointed_wal_writes_and_retries_permission_error(
        self, tmp_path, user, monkeypatch
    ):
        base_migration = _BaseSchemaMigration("v0 Genesis")
        second_migration = _NoOpMigration("v0.2.0:0_step")
        monkeypatch.setattr(
            manager_module, "versions", [base_migration, second_migration]
        )

        client = DBClient()
        db_manager = DBManager(client)
        await db_manager.initialize(
            DatasourceInitParams.build(user=user, password="secret123")
        )
        async with client.tx() as cursor:
            await cursor.execute("PRAGMA wal_autocheckpoint = 0")
            for idx in range(25):
                await cursor.execute(
                    "INSERT INTO records (val) VALUES (?)", (f"wal-row-{idx}",)
                )

        monkeypatch.setattr(
            manager_module,
            "versions",
            [base_migration, _FailingMigration("v0.2.0:0_step")],
        )

        real_replace = manager_module.os.replace
        replace_calls = {"count": 0}

        def _flaky_replace(src, dst):
            replace_calls["count"] += 1
            if replace_calls["count"] < 3:
                raise PermissionError(32, "The process cannot access the file")
            return real_replace(src, dst)

        monkeypatch.setattr(manager_module.os, "replace", _flaky_replace)
        monkeypatch.setattr(manager_module.time, "sleep", lambda _s: None)

        older_payload = _build_sqlite_payload(
            tmp_path,
            "older_wal_backup.db",
            ["v0 Genesis"],
            record_values=("should-not-persist",),
        )

        with pytest.raises(MigrationError, match="v0.2.0:0_step"):
            await db_manager.import_data(older_payload, initialize=False)

        assert replace_calls["count"] == 3
        assert db_manager.unlocked is True
        assert not (user.path / "data.db.tmp").exists()
        async with client.read() as cursor:
            await cursor.execute("SELECT COUNT(*) FROM records")
            count = (await cursor.fetchone())[0]
        assert count == 25
        await db_manager.lock()
