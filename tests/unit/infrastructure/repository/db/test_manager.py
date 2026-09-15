import uuid

import pytest

from domain.data_init import DatasourceInitParams, MigrationError
from domain.user import User
from infrastructure.repository.db import manager as manager_module
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.manager import DBManager
from infrastructure.repository.db.upgrader import DBVersionMigration


class _FailingMigration(DBVersionMigration):
    @property
    def name(self):
        return "failing_migration"

    async def upgrade(self, cursor, context):
        raise RuntimeError("boom")


@pytest.fixture
def user(tmp_path):
    return User(
        id=uuid.uuid4(),
        username="testuser",
        path=tmp_path,
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
