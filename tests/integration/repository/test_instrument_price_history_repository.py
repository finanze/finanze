import sqlite3
from datetime import date

import pytest
import pytest_asyncio

from domain.dezimal import Dezimal
from domain.instrument_history import InstrumentPricePoint
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.instrument_history.instrument_price_history_repository import (
    InstrumentPriceHistorySQLRepository,
)

_SCHEMA = """
    CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE instrument_price_history (
        id CHAR(36) PRIMARY KEY,
        instrument_key VARCHAR(255) NOT NULL,
        date DATE NOT NULL,
        price TEXT NOT NULL,
        currency CHAR(3) NOT NULL,
        source VARCHAR(64) NOT NULL,
        created_at TIMESTAMP NOT NULL,
        UNIQUE (instrument_key, date)
    );
    CREATE TABLE instrument_symbol_map (
        id CHAR(36) PRIMARY KEY,
        instrument_key VARCHAR(255) NOT NULL UNIQUE,
        symbol VARCHAR(64) NOT NULL,
        source VARCHAR(64) NOT NULL,
        resolved_at TIMESTAMP NOT NULL
    );
    CREATE TABLE instrument_split_cache (
        id CHAR(36) PRIMARY KEY,
        instrument_key VARCHAR(255) NOT NULL,
        date DATE NOT NULL,
        ratio TEXT NOT NULL,
        UNIQUE (instrument_key, date)
    );
    CREATE TABLE instrument_split_checked (
        id CHAR(36) PRIMARY KEY,
        instrument_key VARCHAR(255) NOT NULL UNIQUE,
        checked_at TIMESTAMP NOT NULL
    );
"""


@pytest_asyncio.fixture
async def setup():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(_SCHEMA)
    yield InstrumentPriceHistorySQLRepository(DBClient(connection))
    connection.close()


@pytest.mark.asyncio
async def test_upsert_and_read_history(setup):
    repository = setup
    points = [
        InstrumentPricePoint(date=date(2025, 1, 1), price=Dezimal(100), currency="EUR"),
        InstrumentPricePoint(date=date(2025, 1, 2), price=Dezimal(101), currency="EUR"),
    ]

    await repository.upsert("IE00TEST", points, source="yfinance")
    stored = await repository.get_history(
        "IE00TEST", date(2025, 1, 1), date(2025, 1, 10)
    )

    assert [point.price for point in stored] == [Dezimal(100), Dezimal(101)]

    await repository.upsert(
        "IE00TEST",
        [
            InstrumentPricePoint(
                date=date(2025, 1, 1), price=Dezimal(102), currency="EUR"
            )
        ],
        source="yfinance",
    )
    stored = await repository.get_history(
        "IE00TEST", date(2025, 1, 1), date(2025, 1, 10)
    )
    assert stored[0].price == Dezimal(102)


@pytest.mark.asyncio
async def test_resolved_symbol_roundtrip(setup):
    repository = setup

    assert await repository.get_resolved_symbol("IE00TEST") is None

    await repository.save_resolved_symbol("IE00TEST", "IE00TEST.F", source="yfinance")
    assert await repository.get_resolved_symbol("IE00TEST") == (
        "IE00TEST.F",
        "yfinance",
    )

    await repository.save_resolved_symbol("IE00TEST", "IE00TEST.DE", source="yfinance")
    assert await repository.get_resolved_symbol("IE00TEST") == (
        "IE00TEST.DE",
        "yfinance",
    )


@pytest.mark.asyncio
async def test_splits_roundtrip(setup):
    from domain.instrument_history import InstrumentSplit

    repository = setup

    assert await repository.is_splits_checked("IE00TEST") is False
    assert await repository.get_splits("IE00TEST") == []

    await repository.save_splits(
        "IE00TEST", [InstrumentSplit(date=date(2025, 6, 19), ratio=Dezimal(10))]
    )
    await repository.mark_splits_checked("IE00TEST")

    assert await repository.is_splits_checked("IE00TEST") is True
    stored = await repository.get_splits("IE00TEST")
    assert stored[0].ratio == Dezimal(10)
