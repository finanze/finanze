import sqlite3

import pytest
import pytest_asyncio

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v10.v0101_1_transaction_split_ratio import (
    V01011TransactionSplitRatio,
)


@pytest_asyncio.fixture
async def setup():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE investment_transactions (id TEXT PRIMARY KEY, amount TEXT NOT NULL)"
    )
    connection.execute("CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT)")
    connection.execute(
        "INSERT INTO investment_transactions (id, amount) VALUES ('existing', '25.00')"
    )
    connection.commit()
    client = DBClient(connection)
    async with client.tx() as cursor:
        await V01011TransactionSplitRatio().upgrade(
            cursor, DatasourceInitContext(config=None)
        )
    yield connection
    connection.close()


@pytest.mark.asyncio
async def test_adds_nullable_split_ratio_without_changing_existing_transactions(setup):
    connection = setup

    columns = {
        row["name"]: row
        for row in connection.execute("PRAGMA table_info(investment_transactions)")
    }
    assert columns["split_ratio"]["notnull"] == 0

    row = connection.execute(
        "SELECT amount, split_ratio FROM investment_transactions WHERE id = 'existing'"
    ).fetchone()
    assert row["amount"] == "25.00"
    assert row["split_ratio"] is None
