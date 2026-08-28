import sqlite3

import pytest
import pytest_asyncio

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v10.v0100_7_include_wallet_tokens import (
    V01007IncludeWalletTokens,
)

_SCHEMA = """
    CREATE TABLE entities (
        id CHAR(36) PRIMARY KEY,
        name TEXT NOT NULL,
        natural_id TEXT,
        type VARCHAR(64) NOT NULL,
        origin VARCHAR(32) NOT NULL
    );
    CREATE TABLE crypto_wallets (
        id              CHAR(36)     NOT NULL PRIMARY KEY,
        entity_id       CHAR(36)     NOT NULL,
        name            TEXT         NOT NULL,
        address_source  VARCHAR(20)  NOT NULL,
        created_at      TIMESTAMP    NOT NULL
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
async def test_adds_include_wallet_tokens_column(setup):
    db_client, conn = setup

    migration = V01007IncludeWalletTokens()
    async with db_client.tx() as cursor:
        await migration.upgrade(cursor, DatasourceInitContext(config=None))

    columns = {row["name"] for row in conn.execute("PRAGMA table_info(crypto_wallets)")}
    assert "include_wallet_tokens" in columns


@pytest.mark.asyncio
async def test_include_wallet_tokens_defaults_to_zero(setup):
    db_client, conn = setup

    migration = V01007IncludeWalletTokens()
    async with db_client.tx() as cursor:
        await migration.upgrade(cursor, DatasourceInitContext(config=None))

    conn.execute(
        "INSERT INTO crypto_wallets (id, entity_id, name, address_source, created_at) "
        "VALUES ('w1', 'e1', 'Wallet', 'MANUAL', '2024-01-01')"
    )
    row = conn.execute(
        "SELECT include_wallet_tokens FROM crypto_wallets WHERE id = 'w1'"
    ).fetchone()
    assert row["include_wallet_tokens"] == 0
