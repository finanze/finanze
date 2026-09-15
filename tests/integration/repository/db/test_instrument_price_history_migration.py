import sqlite3

import pytest
import pytest_asyncio

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v10.v0100_3_instrument_price_history import (
    V01003InstrumentPriceHistory,
)


@pytest_asyncio.fixture
async def setup():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT)")
    client = DBClient(connection)
    yield client, connection
    connection.close()


@pytest.mark.asyncio
async def test_creates_instrument_price_history_table(setup):
    client, connection = setup
    migration = V01003InstrumentPriceHistory()

    async with client.tx() as cursor:
        await migration.upgrade(cursor, DatasourceInitContext(config=None))

    tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "instrument_price_history" in tables

    connection.execute(
        "INSERT INTO instrument_price_history "
        "(id, instrument_key, date, price, currency, source, created_at) "
        "VALUES ('id-1', 'IE00TEST', '2025-01-01', '100.5', 'EUR', 'yfinance', CURRENT_TIMESTAMP)"
    )
    connection.commit()
    row = connection.execute(
        "SELECT price, currency FROM instrument_price_history WHERE instrument_key = 'IE00TEST'"
    ).fetchone()
    assert row["price"] == "100.5"
    assert row["currency"] == "EUR"


@pytest.mark.asyncio
async def test_creates_instrument_symbol_map_table(setup):
    client, connection = setup
    migration = V01003InstrumentPriceHistory()

    async with client.tx() as cursor:
        await migration.upgrade(cursor, DatasourceInitContext(config=None))

    tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "instrument_symbol_map" in tables
    assert "instrument_split_cache" in tables
    assert "instrument_split_checked" in tables

    connection.execute(
        "INSERT INTO instrument_symbol_map "
        "(id, instrument_key, symbol, source, resolved_at) "
        "VALUES ('id-1', 'IE00TEST', 'IE00TEST.F', 'yfinance', CURRENT_TIMESTAMP)"
    )
    connection.commit()
    row = connection.execute(
        "SELECT symbol FROM instrument_symbol_map WHERE instrument_key = 'IE00TEST'"
    ).fetchone()
    assert row["symbol"] == "IE00TEST.F"

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO instrument_symbol_map "
            "(id, instrument_key, symbol, source, resolved_at) "
            "VALUES ('id-2', 'IE00TEST', 'IE00TEST.DE', 'yfinance', CURRENT_TIMESTAMP)"
        )


@pytest.mark.asyncio
async def test_enforces_unique_instrument_date(setup):
    client, connection = setup
    migration = V01003InstrumentPriceHistory()

    async with client.tx() as cursor:
        await migration.upgrade(cursor, DatasourceInitContext(config=None))

    connection.execute(
        "INSERT INTO instrument_price_history "
        "(id, instrument_key, date, price, currency, source, created_at) "
        "VALUES ('id-1', 'IE00TEST', '2025-01-01', '100', 'EUR', 'yfinance', CURRENT_TIMESTAMP)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO instrument_price_history "
            "(id, instrument_key, date, price, currency, source, created_at) "
            "VALUES ('id-2', 'IE00TEST', '2025-01-01', '101', 'EUR', 'yfinance', CURRENT_TIMESTAMP)"
        )
