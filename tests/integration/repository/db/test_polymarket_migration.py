import sqlite3

import pytest
import pytest_asyncio

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v10.v0100_1_polymarket import (
    V01001Polymarket,
)

_SCHEMA = """
    CREATE TABLE entities (
        id CHAR(36) PRIMARY KEY,
        name TEXT NOT NULL,
        natural_id TEXT,
        type VARCHAR(64) NOT NULL,
        origin VARCHAR(32) NOT NULL
    );
    CREATE TABLE global_positions (
        id CHAR(36) PRIMARY KEY,
        entity_id CHAR(36) NOT NULL,
        date DATETIME NOT NULL,
        source VARCHAR(255) NOT NULL,
        entity_account_id CHAR(36)
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
async def test_creates_normalized_market_forecast_schema(setup):
    db_client, conn = setup

    migration = V01001Polymarket()
    async with db_client.tx() as cursor:
        await migration.upgrade(cursor, DatasourceInitContext(config=None))

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(market_forecast_positions)")
    }
    assert columns == {
        "id",
        "global_position_id",
        "size",
        "entry_price",
        "currency",
        "mark_price",
        "market_value",
        "unrealized_pnl",
        "expiry",
        "name",
        "initial_investment",
        "market_key",
        "event_key",
        "outcome_key",
        "market_url",
        "icon_url",
        "outcome",
    }
