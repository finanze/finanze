import sqlite3

import pytest
import pytest_asyncio

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v10.v0100_6_zerion_integration import (
    V01006ZerionIntegration,
)

_SCHEMA = """
    CREATE TABLE external_integrations
    (
        id     VARCHAR(36) NOT NULL PRIMARY KEY,
        name   VARCHAR(48) NOT NULL,
        type   VARCHAR(32) NOT NULL,
        status VARCHAR(32) NOT NULL
    );
    CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT);
"""


@pytest_asyncio.fixture
async def setup():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    db_client = DBClient(conn)
    yield db_client, conn
    conn.close()


@pytest.mark.asyncio
async def test_seeds_zerion_crypto_provider_integration(setup):
    db_client, conn = setup

    migration = V01006ZerionIntegration()
    async with db_client.tx() as cursor:
        await migration.upgrade(cursor, DatasourceInitContext(config=None))

    row = conn.execute(
        "SELECT id, name, type, status FROM external_integrations WHERE id = 'ZERION'"
    ).fetchone()

    assert row is not None
    assert row["id"] == "ZERION"
    assert row["name"] == "Zerion"
    assert row["type"] == "CRYPTO_PROVIDER"
    assert row["status"] == "OFF"
