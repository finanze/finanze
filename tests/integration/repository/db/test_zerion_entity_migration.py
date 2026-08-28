import sqlite3

import pytest

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v10.v0100_8_zerion_entity import (
    V01008ZerionEntity,
)

_SCHEMA = """
CREATE TABLE entities (
    id CHAR(36) NOT NULL PRIMARY KEY,
    name TEXT NOT NULL,
    natural_id TEXT,
    type VARCHAR(40) NOT NULL,
    origin VARCHAR(20) NOT NULL
);
"""


@pytest.mark.asyncio
async def test_seeds_zerion_crypto_wallet_entity():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    db = DBClient(conn)

    async with db.tx(skip_last_update=True) as cursor:
        await V01008ZerionEntity().upgrade(cursor, DatasourceInitContext(config=None))

    row = conn.execute(
        "SELECT * FROM entities WHERE id = 'c0000000-0000-0000-0000-000000000006'"
    ).fetchone()
    assert row is not None
    assert row["name"] == "Zerion"
    assert row["type"] == "CRYPTO_WALLET"
    assert row["origin"] == "NATIVE"


@pytest.mark.asyncio
async def test_zerion_entity_seed_is_idempotent():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    db = DBClient(conn)

    async with db.tx(skip_last_update=True) as cursor:
        await V01008ZerionEntity().upgrade(cursor, DatasourceInitContext(config=None))
    async with db.tx(skip_last_update=True) as cursor:
        await V01008ZerionEntity().upgrade(cursor, DatasourceInitContext(config=None))

    count = conn.execute(
        "SELECT COUNT(*) AS c FROM entities WHERE id = 'c0000000-0000-0000-0000-000000000006'"
    ).fetchone()["c"]
    assert count == 1
