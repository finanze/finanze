import sqlite3
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

import application.use_cases.get_gains_timeline as gains_module
from application.use_cases.get_gains_timeline import GetGainsTimelineImpl
from domain.dezimal import Dezimal
from domain.instrument import InstrumentDataRequest, InstrumentType
from domain.instrument_history import InstrumentPricePoint, InstrumentSplit
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
        checked_at TIMESTAMP NOT NULL,
        checked_from DATE,
        checked_to DATE
    );
"""


@pytest_asyncio.fixture
async def setup():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(_SCHEMA)
    yield InstrumentPriceHistorySQLRepository(DBClient(connection))
    connection.close()


@pytest_asyncio.fixture
async def connected():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(_SCHEMA)
    yield InstrumentPriceHistorySQLRepository(DBClient(connection)), connection
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


@pytest.mark.asyncio
async def test_split_check_requires_coverage_of_requested_range(setup):
    repository = setup
    first_day = date(2025, 1, 1)
    last_day = date(2025, 12, 31)
    await repository.mark_splits_checked("IE00TEST")
    assert not await repository.is_splits_checked("IE00TEST", first_day, last_day)

    await repository.mark_splits_checked("IE00TEST", first_day, last_day)

    assert await repository.is_splits_checked("IE00TEST", first_day, last_day)
    assert await repository.is_splits_checked(
        "IE00TEST", date(2025, 2, 1), date(2025, 11, 30)
    )
    assert not await repository.is_splits_checked(
        "IE00TEST", date(2024, 12, 31), last_day
    )
    assert not await repository.is_splits_checked(
        "IE00TEST", first_day, date(2026, 1, 1)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("first", "second", "covered", "uncovered"),
    [
        pytest.param(
            (date(2024, 1, 1), date(2025, 6, 30)),
            (date(2025, 1, 1), date(2025, 7, 31)),
            (date(2024, 1, 1), date(2025, 7, 31)),
            (date(2023, 12, 31), date(2025, 7, 31)),
            id="overlapping",
        ),
        pytest.param(
            (date(2024, 1, 1), date(2024, 12, 31)),
            (date(2025, 1, 1), date(2025, 7, 31)),
            (date(2024, 1, 1), date(2025, 7, 31)),
            (date(2024, 1, 1), date(2025, 8, 1)),
            id="adjacent",
        ),
        pytest.param(
            (date(2024, 1, 1), date(2025, 7, 31)),
            (date(2024, 6, 1), date(2025, 3, 31)),
            (date(2024, 1, 1), date(2025, 7, 31)),
            (date(2023, 12, 31), date(2025, 7, 31)),
            id="contained",
        ),
        pytest.param(
            (date(2025, 1, 1), date(2025, 7, 31)),
            (date(2024, 1, 1), date(2025, 7, 31)),
            (date(2024, 1, 1), date(2025, 7, 31)),
            (date(2023, 12, 31), date(2025, 7, 31)),
            id="wider",
        ),
    ],
)
async def test_split_check_keeps_contiguous_coverage(
    setup, first, second, covered, uncovered
):
    repository = setup

    await repository.mark_splits_checked("IE00TEST", *first)
    await repository.mark_splits_checked("IE00TEST", *second)

    assert await repository.is_splits_checked("IE00TEST", *covered)
    assert not await repository.is_splits_checked("IE00TEST", *uncovered)


@pytest.mark.asyncio
async def test_split_check_restarts_coverage_after_a_gap(setup):
    repository = setup

    await repository.mark_splits_checked(
        "IE00TEST", date(2024, 1, 1), date(2024, 6, 30)
    )
    await repository.mark_splits_checked(
        "IE00TEST", date(2025, 1, 1), date(2025, 7, 31)
    )

    assert not await repository.is_splits_checked(
        "IE00TEST", date(2024, 1, 1), date(2025, 7, 31)
    )
    assert await repository.is_splits_checked(
        "IE00TEST", date(2025, 1, 1), date(2025, 7, 31)
    )


@pytest.mark.asyncio
async def test_split_check_without_range_drops_recorded_coverage(setup):
    repository = setup

    await repository.mark_splits_checked(
        "IE00TEST", date(2024, 1, 1), date(2025, 7, 31)
    )
    await repository.mark_splits_checked("IE00TEST")

    assert await repository.is_splits_checked("IE00TEST")
    assert not await repository.is_splits_checked(
        "IE00TEST", date(2024, 1, 1), date(2025, 7, 31)
    )


@pytest.mark.asyncio
async def test_ranged_split_check_replaces_legacy_row(setup):
    repository = setup

    await repository.mark_splits_checked("IE00TEST")
    await repository.mark_splits_checked(
        "IE00TEST", date(2025, 1, 1), date(2025, 7, 31)
    )

    assert await repository.is_splits_checked(
        "IE00TEST", date(2025, 1, 1), date(2025, 7, 31)
    )
    assert not await repository.is_splits_checked(
        "IE00TEST", date(2024, 12, 31), date(2025, 7, 31)
    )


@pytest.mark.asyncio
async def test_split_checks_are_scoped_by_instrument(setup):
    repository = setup

    await repository.mark_splits_checked(
        "IE00TEST", date(2024, 1, 1), date(2025, 7, 31)
    )

    assert not await repository.is_splits_checked(
        "IE00OTHER", date(2024, 1, 1), date(2025, 7, 31)
    )


@pytest.mark.asyncio
async def test_split_check_expires_after_a_week(connected):
    repository, connection = connected
    await repository.mark_splits_checked(
        "IE00TEST", date(2024, 1, 1), date(2025, 7, 31)
    )

    connection.execute(
        "UPDATE instrument_split_checked SET checked_at = datetime('now', '-6 days')"
    )
    connection.commit()
    assert await repository.is_splits_checked(
        "IE00TEST", date(2024, 1, 1), date(2025, 7, 31)
    )

    connection.execute(
        "UPDATE instrument_split_checked SET checked_at = datetime('now', '-8 days')"
    )
    connection.commit()
    assert not await repository.is_splits_checked(
        "IE00TEST", date(2024, 1, 1), date(2025, 7, 31)
    )


@pytest.mark.asyncio
async def test_expired_split_check_keeps_older_coverage_once_refreshed(connected):
    repository, connection = connected
    await repository.mark_splits_checked(
        "IE00TEST", date(2024, 1, 1), date(2025, 7, 31)
    )
    connection.execute(
        "UPDATE instrument_split_checked SET checked_at = datetime('now', '-8 days')"
    )
    connection.commit()

    await repository.mark_splits_checked(
        "IE00TEST", date(2025, 6, 1), date(2025, 8, 15)
    )

    assert await repository.is_splits_checked(
        "IE00TEST", date(2024, 1, 1), date(2025, 8, 15)
    )


class _FrozenDatetime(datetime):
    frozen = date.today()

    @classmethod
    def now(cls, tz=None):
        moment = datetime(cls.frozen.year, cls.frozen.month, cls.frozen.day, 12)
        return moment.replace(tzinfo=tz)


def _freeze(monkeypatch, day):
    monkeypatch.setattr(
        gains_module,
        "datetime",
        type("FrozenDatetime", (_FrozenDatetime,), {"frozen": day}),
    )


def _split_use_case(repository, splits):
    provider = AsyncMock()
    provider.get_splits.return_value = splits
    return (
        GetGainsTimelineImpl(
            AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock(), provider, repository
        ),
        provider,
    )


@pytest.mark.asyncio
async def test_gains_split_lookup_repeats_weekly(connected, monkeypatch):
    repository, connection = connected
    split = InstrumentSplit(date=date(2025, 6, 2), ratio=Dezimal(2))
    use_case, provider = _split_use_case(repository, [split])
    request = InstrumentDataRequest(type=InstrumentType.STOCK, ticker="ACME")
    windows = {"ACME": (date(2025, 1, 1), date(2025, 12, 31))}
    today = date.today()

    for offset in (0, 1, 3, 6):
        _freeze(monkeypatch, today + timedelta(days=offset))
        splits = await use_case._load_splits({"ACME": request}, windows)
        assert splits == {"ACME": {split.date: split.ratio}}
    assert provider.get_splits.await_count == 1

    connection.execute(
        "UPDATE instrument_split_checked SET checked_at = datetime('now', '-8 days')"
    )
    connection.commit()
    await use_case._load_splits({"ACME": request}, windows)

    assert provider.get_splits.await_count == 2


@pytest.mark.asyncio
async def test_gains_split_lookup_keeps_wide_coverage_after_narrow_refresh(
    connected, monkeypatch
):
    repository, connection = connected
    use_case, provider = _split_use_case(repository, [])
    request = InstrumentDataRequest(type=InstrumentType.STOCK, ticker="ACME")
    wide = {"ACME": (date(2024, 1, 1), date(2025, 12, 31))}
    narrow = {"ACME": (date(2025, 6, 1), date(2025, 12, 31))}
    _freeze(monkeypatch, date.today())

    await use_case._load_splits({"ACME": request}, wide)
    connection.execute(
        "UPDATE instrument_split_checked SET checked_at = datetime('now', '-8 days')"
    )
    connection.commit()
    await use_case._load_splits({"ACME": request}, narrow)
    await use_case._load_splits({"ACME": request}, wide)

    assert provider.get_splits.await_count == 2
