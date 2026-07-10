import json
import sqlite3
from uuid import uuid4

import pytest
import pytest_asyncio

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v09.v090_3_valuation_market_value import (
    V0903ValuationMarketValue,
)

_SCHEMA = """
    CREATE TABLE real_estate (
        id CHAR(36) PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        currency CHAR(3) NOT NULL,
        purchase_date DATE NOT NULL,
        purchase_price TEXT NOT NULL,
        estimated_market_value TEXT NOT NULL,
        valuations JSON NOT NULL
    );
    CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT);
"""


def _insert_re(conn, purchase_date, estimated_market_value, valuations):
    re_id = str(uuid4())
    conn.execute(
        "INSERT INTO real_estate "
        "(id, name, currency, purchase_date, purchase_price, estimated_market_value, valuations) "
        "VALUES (?, 'House', 'EUR', ?, '100000', ?, ?)",
        (re_id, purchase_date, estimated_market_value, json.dumps(valuations)),
    )
    return re_id


@pytest_asyncio.fixture
async def setup():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    db_client = DBClient(conn)
    yield db_client, conn
    conn.close()


class TestValuationMarketValueMigration:
    @pytest.mark.asyncio
    async def test_backfills_market_value_when_none_marked(self, setup):
        db_client, conn = setup
        re_id = _insert_re(conn, "2020-01-15", "250000", [])
        conn.commit()

        migration = V0903ValuationMarketValue()
        async with db_client.tx() as cursor:
            await migration.upgrade(cursor, DatasourceInitContext(config=None))

        row = conn.execute(
            "SELECT valuations FROM real_estate WHERE id = ?", (re_id,)
        ).fetchone()
        valuations = json.loads(row["valuations"])
        assert len(valuations) == 1
        assert valuations[0]["market_value"] is True
        assert valuations[0]["date"] == "2020-01-15"
        assert valuations[0]["amount"] == "250000"

    @pytest.mark.asyncio
    async def test_adds_flag_to_existing_valuations_and_backfills(self, setup):
        db_client, conn = setup
        re_id = _insert_re(
            conn,
            "2019-06-01",
            "600000",
            [{"date": "2023-01-01", "amount": "550000", "notes": None}],
        )
        conn.commit()

        migration = V0903ValuationMarketValue()
        async with db_client.tx() as cursor:
            await migration.upgrade(cursor, DatasourceInitContext(config=None))

        row = conn.execute(
            "SELECT valuations FROM real_estate WHERE id = ?", (re_id,)
        ).fetchone()
        valuations = json.loads(row["valuations"])
        # The pre-existing valuation gets a market_value flag and a backfilled
        # market-value valuation is appended at the purchase date.
        assert len(valuations) == 2
        assert valuations[0]["market_value"] is False
        backfilled = valuations[1]
        assert backfilled["market_value"] is True
        assert backfilled["date"] == "2019-06-01"
        assert backfilled["amount"] == "600000"

    @pytest.mark.asyncio
    async def test_does_not_backfill_when_already_marked(self, setup):
        db_client, conn = setup
        re_id = _insert_re(
            conn,
            "2019-06-01",
            "600000",
            [
                {
                    "date": "2023-01-01",
                    "amount": "550000",
                    "notes": None,
                    "market_value": True,
                }
            ],
        )
        conn.commit()

        migration = V0903ValuationMarketValue()
        async with db_client.tx() as cursor:
            await migration.upgrade(cursor, DatasourceInitContext(config=None))

        row = conn.execute(
            "SELECT valuations FROM real_estate WHERE id = ?", (re_id,)
        ).fetchone()
        valuations = json.loads(row["valuations"])
        assert len(valuations) == 1
        assert valuations[0]["market_value"] is True
