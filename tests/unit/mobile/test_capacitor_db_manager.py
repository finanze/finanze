import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from domain.data_init import DatasourceInitParams, DecryptionError
from domain.user import User


_MOBILE_ROOT = (
    Path(__file__).resolve().parents[3]
    / "frontend/app/src/python/finanze/infrastructure/repository/db"
)


@pytest.fixture
def mobile_db(monkeypatch, tmp_path):
    sqlite = SimpleNamespace(openDatabase=AsyncMock(), executeSql=AsyncMock())
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
