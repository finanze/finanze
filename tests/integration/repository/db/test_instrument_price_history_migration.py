import sqlite3

import pytest
import pytest_asyncio

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v10.v0100_3_instrument_price_history import (
    V01003InstrumentPriceHistory,
)
from infrastructure.repository.db.versions.v0.v11.v0110_9_split_cache_coverage import (
    V01109SplitCacheCoverage,
)


@pytest_asyncio.fixture
async def setup():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT)")
    connection.executescript(
        "CREATE TABLE stock_positions (isin TEXT, ticker TEXT, name TEXT);"
        "CREATE TABLE fund_positions (isin TEXT, name TEXT);"
        "CREATE TABLE investment_transactions (product_type TEXT, isin TEXT, ticker TEXT, name TEXT);"
    )
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


@pytest.mark.asyncio
async def test_split_coverage_migration_preserves_legacy_cache(setup):
    client, connection = setup
    async with client.tx() as cursor:
        await V01003InstrumentPriceHistory().upgrade(
            cursor, DatasourceInitContext(config=None)
        )
        await cursor.execute(
            "INSERT INTO instrument_split_checked (id, instrument_key, checked_at) "
            "VALUES ('id-1', 'IE00TEST', CURRENT_TIMESTAMP)"
        )
        await V01109SplitCacheCoverage().upgrade(
            cursor, DatasourceInitContext(config=None)
        )

    row = connection.execute(
        "SELECT checked_from, checked_to FROM instrument_split_checked "
        "WHERE instrument_key = 'IE00TEST'"
    ).fetchone()
    assert row is not None
    assert row["checked_from"] is None
    assert row["checked_to"] is None


@pytest.mark.asyncio
async def test_split_coverage_migration_scopes_unambiguous_price_caches(setup):
    client, connection = setup
    async with client.tx() as cursor:
        await V01003InstrumentPriceHistory().upgrade(
            cursor, DatasourceInitContext(config=None)
        )
        await cursor.execute(
            "INSERT INTO stock_positions (isin, ticker, name) VALUES "
            "('STOCK', NULL, 'Stock'), ('SHARED', NULL, 'Shared stock')"
        )
        await cursor.execute(
            "INSERT INTO fund_positions (isin, name) VALUES "
            "('FUND', 'Fund'), ('SHARED', 'Shared fund')"
        )
        for asset_key in ("STOCK", "FUND", "SHARED"):
            await cursor.execute(
                "INSERT INTO instrument_price_history "
                "(id, instrument_key, date, price, currency, source, created_at) "
                "VALUES (?, ?, '2025-01-01', '100', 'EUR', 'test', CURRENT_TIMESTAMP)",
                (asset_key, asset_key),
            )
        await cursor.execute(
            "INSERT INTO instrument_symbol_map "
            "(id, instrument_key, symbol, source, resolved_at) "
            "VALUES ('symbol', 'FUND', 'FUND.TEST', 'test', CURRENT_TIMESTAMP)"
        )
        await cursor.execute(
            "INSERT INTO instrument_no_result (id, instrument_key, marked_at) "
            "VALUES ('negative', 'STOCK', CURRENT_TIMESTAMP)"
        )
        await V01109SplitCacheCoverage().upgrade(
            cursor, DatasourceInitContext(config=None)
        )

    keys = {
        row["instrument_key"]
        for row in connection.execute(
            "SELECT instrument_key FROM instrument_price_history"
        )
    }
    assert keys == {"STOCK_ETF:STOCK", "FUND:FUND", "SHARED"}
    assert (
        connection.execute(
            "SELECT instrument_key FROM instrument_symbol_map"
        ).fetchone()[0]
        == "FUND:FUND"
    )
    assert (
        connection.execute(
            "SELECT instrument_key FROM instrument_no_result"
        ).fetchone()[0]
        == "STOCK_ETF:STOCK"
    )
