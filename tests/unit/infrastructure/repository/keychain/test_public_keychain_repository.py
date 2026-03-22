import sqlite3
from datetime import datetime

import pytest
from dateutil.tz import tzlocal

from domain.public_keychain import PublicKeyEntry
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.keychain.public_keychain_repository import (
    PublicKeychainRepository,
)

CREATE_TABLE_SQL = """
CREATE TABLE public_keychain (
    key        VARCHAR(64) PRIMARY KEY,
    value      VARCHAR(256) NOT NULL,
    algo       INTEGER NOT NULL,
    version    INTEGER NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
"""


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(CREATE_TABLE_SQL)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sys_config (key TEXT PRIMARY KEY, value TEXT)"
    )
    conn.commit()
    yield DBClient(connection=conn)
    conn.close()


def _entry(key="k1", value="val", algo=1, version=1):
    return PublicKeyEntry(
        key=key,
        value=value,
        algo=algo,
        version=version,
        updated_at=datetime.now(tzlocal()),
    )


class TestSaveAndRetrieve:
    @pytest.mark.asyncio
    async def test_save_and_retrieve_entries(self, db):
        repo = PublicKeychainRepository(client=db)

        entries = [_entry("k1", "v1"), _entry("k2", "v2")]
        await repo.save(entries)

        result = await repo.retrieve()
        assert len(result) == 2
        keys = {e.key for e in result}
        assert keys == {"k1", "k2"}

    @pytest.mark.asyncio
    async def test_retrieve_empty(self, db):
        repo = PublicKeychainRepository(client=db)
        result = await repo.retrieve()
        assert result == []


class TestUpsert:
    @pytest.mark.asyncio
    async def test_save_updates_existing_entry(self, db):
        repo = PublicKeychainRepository(client=db)

        await repo.save([_entry("k1", "old_value", algo=1, version=1)])
        await repo.save([_entry("k1", "new_value", algo=1, version=2)])

        result = await repo.retrieve()
        assert len(result) == 1
        assert result[0].value == "new_value"
        assert result[0].version == 2


class TestRetrievePreservesFields:
    @pytest.mark.asyncio
    async def test_all_fields_persisted(self, db):
        repo = PublicKeychainRepository(client=db)
        now = datetime.now(tzlocal())
        entry = PublicKeyEntry(
            key="mykey", value="myval", algo=1, version=5, updated_at=now
        )

        await repo.save([entry])
        result = await repo.retrieve()

        assert len(result) == 1
        r = result[0]
        assert r.key == "mykey"
        assert r.value == "myval"
        assert r.algo == 1
        assert r.version == 5
