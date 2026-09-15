import sqlite3

import pytest
import pytest_asyncio

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v10.v0100_2_clear_sego_real_txs import (
    V01002ClearSegoRealTransactions,
)

_SEGO_ENTITY_ID = "e0000000-0000-0000-0000-000000000006"
_OTHER_ENTITY_ID = "e0000000-0000-0000-0000-000000000001"

_SCHEMA = """
    CREATE TABLE investment_transactions (
        id TEXT PRIMARY KEY,
        entity_id TEXT NOT NULL,
        source TEXT NOT NULL
    );
"""


@pytest_asyncio.fixture
async def setup():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(_SCHEMA)
    client = DBClient(connection)
    yield client, connection
    connection.close()


@pytest.mark.asyncio
async def test_clears_only_real_sego_investment_transactions(setup):
    client, connection = setup
    connection.executemany(
        "INSERT INTO investment_transactions (id, entity_id, source) VALUES (?, ?, ?)",
        [
            ("sego-real", _SEGO_ENTITY_ID, "REAL"),
            ("sego-manual", _SEGO_ENTITY_ID, "MANUAL"),
            ("other-real", _OTHER_ENTITY_ID, "REAL"),
        ],
    )
    connection.commit()

    migration = V01002ClearSegoRealTransactions()
    async with client.tx(skip_last_update=True) as cursor:
        await migration.upgrade(cursor, DatasourceInitContext(config=None))

    rows = connection.execute(
        "SELECT id FROM investment_transactions ORDER BY id"
    ).fetchall()
    assert [row["id"] for row in rows] == ["other-real", "sego-manual"]
