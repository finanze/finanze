import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from domain.data_init import DatasourceInitParams, DecryptionError, MigrationAheadOfTime
from domain.user import User
from infrastructure.repository.db.version_registry import get_schema_version


_MOBILE_ROOT = (
    Path(__file__).resolve().parents[3]
    / "frontend/app/src/python/finanze/infrastructure/repository/db"
)


@pytest.fixture
def mobile_db(monkeypatch, tmp_path):
    sqlite = SimpleNamespace(
        openDatabase=AsyncMock(),
        executeSql=AsyncMock(),
        exportDatabaseToStaging=AsyncMock(),
        importDatabaseFromStaging=AsyncMock(),
        deleteDatabase=AsyncMock(),
    )
    js_stub = ModuleType("js")
    js_stub.jsBridge = SimpleNamespace(sqlite=sqlite)
    monkeypatch.setitem(sys.modules, "js", js_stub)

    modules = {}
    for name in ("capacitor_client", "capacitor_db_manager"):
        module_name = f"infrastructure.repository.db.{name}"
        spec = spec_from_file_location(module_name, _MOBILE_ROOT / f"{name}.py")
        assert spec is not None and spec.loader is not None
        module = module_from_spec(spec)
        monkeypatch.setitem(sys.modules, module_name, module)
        spec.loader.exec_module(module)
        modules[name] = module

    client = Mock(spec=modules["capacitor_client"].CapacitorDBClient)
    manager = modules["capacitor_db_manager"].CapacitorDBManager(client)
    params = DatasourceInitParams.build(
        user=User(id=uuid4(), username="testuser", path=tmp_path, last_login=None),
        password="WrongPassword789!",
    )
    return manager, client, sqlite, params


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["initialize", "change_password"])
async def test_wrong_key_becomes_decryption_error_and_cleans_up(mobile_db, operation):
    manager, client, sqlite, params = mobile_db
    bridge_error = RuntimeError("Error: [Bridge][sqlite] wrong key for testdb")
    sqlite.openDatabase.side_effect = bridge_error

    with pytest.raises(DecryptionError, match="Incorrect password") as raised:
        if operation == "initialize":
            await manager.initialize(params)
        else:
            await manager.change_password(params, "NewPassword456!")

    assert raised.value.__cause__ is bridge_error
    assert manager.unlocked is False
    client.silent_close.assert_awaited_once()
    client.set_connection.assert_called_once_with(None)
    sqlite.executeSql.assert_not_awaited()
    sqlite.openDatabase.assert_awaited_once_with(
        f"{params.user.hashed_id()}_data.db",
        True,
        "secret",
        1,
        False,
        params.password,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["initialize", "change_password"])
async def test_other_database_error_is_preserved_and_cleans_up(mobile_db, operation):
    manager, client, sqlite, params = mobile_db
    bridge_error = RuntimeError(
        "SetEncryptionSecret: State for: otherSQLite.db not correct"
    )
    sqlite.openDatabase.side_effect = bridge_error

    with pytest.raises(RuntimeError) as raised:
        if operation == "initialize":
            await manager.initialize(params)
        else:
            await manager.change_password(params, "NewPassword456!")

    assert raised.value is bridge_error
    assert manager.unlocked is False
    client.silent_close.assert_awaited_once()
    client.set_connection.assert_called_once_with(None)
    sqlite.executeSql.assert_not_awaited()


def test_get_version_matches_schema_version(mobile_db):
    manager, _, _, _ = mobile_db
    assert manager.get_version() == get_schema_version()


@pytest.mark.asyncio
async def test_import_data_ahead_of_time_initial_cleans_staging_and_raises(
    mobile_db, monkeypatch
):
    manager, _, sqlite, params = mobile_db
    delete_staging_file = AsyncMock()
    processor_mod = ModuleType("infrastructure.cloud.backup.capacitor_backup_processor")
    processor_mod.delete_staging_file = delete_staging_file
    monkeypatch.setitem(
        sys.modules,
        "infrastructure.cloud.backup.capacitor_backup_processor",
        processor_mod,
    )
    sqlite.importDatabaseFromStaging.side_effect = RuntimeError(
        "Error: MIGRATION_AHEAD_OF_TIME:v99.0.0:0_future"
    )
    manager._initialize = AsyncMock()

    with pytest.raises(MigrationAheadOfTime, match="v99.0.0:0_future"):
        await manager.import_data(
            b"", initialize=True, user=params.user, password=params.password
        )

    assert sqlite.importDatabaseFromStaging.await_args.args[4] is True
    delete_staging_file.assert_awaited_once_with("DECOMPILED_DATA")
    manager._initialize.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_data_initial_mid_upgrade_failure_deletes_database(
    mobile_db, monkeypatch
):
    manager, _, sqlite, params = mobile_db
    delete_staging_file = AsyncMock()
    processor_mod = ModuleType("infrastructure.cloud.backup.capacitor_backup_processor")
    processor_mod.delete_staging_file = delete_staging_file
    monkeypatch.setitem(
        sys.modules,
        "infrastructure.cloud.backup.capacitor_backup_processor",
        processor_mod,
    )
    manager._initialize = AsyncMock(side_effect=RuntimeError("mid_upgrade_failure"))

    with pytest.raises(RuntimeError, match="mid_upgrade_failure"):
        await manager.import_data(
            b"", initialize=True, user=params.user, password=params.password
        )

    delete_staging_file.assert_awaited_once_with("DECOMPILED_DATA")
    sqlite.deleteDatabase.assert_awaited_once_with(
        f"{params.user.hashed_id()}_data.db", params.password, True
    )


@pytest.mark.asyncio
async def test_import_data_ahead_of_time_logged_in_reunlocks_and_raises(
    mobile_db, monkeypatch
):
    manager, _, sqlite, params = mobile_db
    delete_staging_file = AsyncMock()
    processor_mod = ModuleType("infrastructure.cloud.backup.capacitor_backup_processor")
    processor_mod.delete_staging_file = delete_staging_file
    monkeypatch.setitem(
        sys.modules,
        "infrastructure.cloud.backup.capacitor_backup_processor",
        processor_mod,
    )
    monkeypatch.setattr(
        sys.modules["infrastructure.repository.db.capacitor_db_manager"],
        "read_settings_rows",
        AsyncMock(return_value=[]),
    )

    manager._user = params.user
    manager._pass = params.password
    manager._unlocked = True
    manager.lock = AsyncMock()
    manager._initialize = AsyncMock()
    sqlite.importDatabaseFromStaging.side_effect = RuntimeError(
        "Error: MIGRATION_AHEAD_OF_TIME:v99.0.0:0_future"
    )

    with pytest.raises(MigrationAheadOfTime, match="v99.0.0:0_future"):
        await manager.import_data(b"", initialize=False)

    sqlite.exportDatabaseToStaging.assert_awaited_once_with("ROLLBACK_DATA")
    assert sqlite.importDatabaseFromStaging.await_count == 1
    assert [c.args[0] for c in delete_staging_file.await_args_list] == [
        "DECOMPILED_DATA",
        "ROLLBACK_DATA",
    ]
    manager._initialize.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_data_mid_upgrade_failure_logged_in_restores_rollback_backup(
    mobile_db, monkeypatch
):
    manager, _, sqlite, params = mobile_db
    delete_staging_file = AsyncMock()
    processor_mod = ModuleType("infrastructure.cloud.backup.capacitor_backup_processor")
    processor_mod.delete_staging_file = delete_staging_file
    monkeypatch.setitem(
        sys.modules,
        "infrastructure.cloud.backup.capacitor_backup_processor",
        processor_mod,
    )
    monkeypatch.setattr(
        sys.modules["infrastructure.repository.db.capacitor_db_manager"],
        "read_settings_rows",
        AsyncMock(return_value=[]),
    )

    manager._user = params.user
    manager._pass = params.password
    manager._unlocked = True
    manager.lock = AsyncMock()
    manager._initialize = AsyncMock(
        side_effect=[RuntimeError("mid_upgrade_failure"), None]
    )

    with pytest.raises(RuntimeError, match="mid_upgrade_failure"):
        await manager.import_data(b"", initialize=False)

    db_name = f"{params.user.hashed_id()}_data.db"
    sqlite.exportDatabaseToStaging.assert_awaited_once_with("ROLLBACK_DATA")
    assert sqlite.importDatabaseFromStaging.await_count == 2
    assert sqlite.importDatabaseFromStaging.await_args_list[1].args == (
        db_name,
        params.password,
        "ROLLBACK_DATA",
    )
    assert manager._initialize.await_count == 2
    assert [c.args[0] for c in delete_staging_file.await_args_list] == [
        "DECOMPILED_DATA",
        "ROLLBACK_DATA",
    ]
