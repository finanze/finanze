from datetime import date
from uuid import uuid4

from application.ports.instrument_price_history_port import InstrumentPriceHistoryPort
from domain.dezimal import Dezimal
from domain.instrument_history import InstrumentPricePoint
from infrastructure.repository.db.client import DBClient


class InstrumentPriceHistorySQLRepository(InstrumentPriceHistoryPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def get_history(
        self, instrument_key: str, from_date: date, to_date: date
    ) -> list[InstrumentPricePoint]:
        sql = (
            "SELECT date, price, currency FROM instrument_price_history "
            "WHERE instrument_key = ? AND date >= ? AND date <= ? ORDER BY date ASC"
        )
        async with self._db_client.read() as cursor:
            await cursor.execute(
                sql, (instrument_key, from_date.isoformat(), to_date.isoformat())
            )
            rows = await cursor.fetchall()
        return [
            InstrumentPricePoint(
                date=date.fromisoformat(row["date"]),
                price=Dezimal(row["price"]),
                currency=row["currency"],
            )
            for row in rows
        ]

    async def upsert(
        self,
        instrument_key: str,
        points: list[InstrumentPricePoint],
        source: str,
    ) -> None:
        if not points:
            return
        sql = (
            "INSERT INTO instrument_price_history "
            "(id, instrument_key, date, price, currency, source, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT (instrument_key, date) DO UPDATE SET "
            "price = excluded.price, currency = excluded.currency, "
            "source = excluded.source"
        )
        async with self._db_client.tx(skip_last_update=True) as cursor:
            for point in points:
                await cursor.execute(
                    sql,
                    (
                        str(uuid4()),
                        instrument_key,
                        point.date.isoformat(),
                        str(point.price),
                        point.currency,
                        source,
                    ),
                )

    async def get_covered_range(self, instrument_key: str) -> tuple[date, date] | None:
        sql = (
            "SELECT MIN(date) AS first_day, MAX(date) AS last_day "
            "FROM instrument_price_history WHERE instrument_key = ?"
        )
        async with self._db_client.read() as cursor:
            await cursor.execute(sql, (instrument_key,))
            row = await cursor.fetchone()
        if not row or row["first_day"] is None:
            return None
        return date.fromisoformat(row["first_day"]), date.fromisoformat(row["last_day"])

    async def get_resolved_symbol(self, instrument_key: str) -> tuple[str, str] | None:
        sql = (
            "SELECT symbol, source FROM instrument_symbol_map WHERE instrument_key = ?"
        )
        async with self._db_client.read() as cursor:
            await cursor.execute(sql, (instrument_key,))
            row = await cursor.fetchone()
        return (row["symbol"], row["source"]) if row else None

    async def save_resolved_symbol(
        self, instrument_key: str, symbol: str, source: str
    ) -> None:
        sql = (
            "INSERT INTO instrument_symbol_map "
            "(id, instrument_key, symbol, source, resolved_at) "
            "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT (instrument_key) DO UPDATE SET "
            "symbol = excluded.symbol, source = excluded.source, "
            "resolved_at = CURRENT_TIMESTAMP"
        )
        async with self._db_client.tx(skip_last_update=True) as cursor:
            await cursor.execute(sql, (str(uuid4()), instrument_key, symbol, source))

    async def get_splits(self, instrument_key: str) -> list:
        from domain.instrument_history import InstrumentSplit

        sql = (
            "SELECT date, ratio FROM instrument_split_cache "
            "WHERE instrument_key = ? ORDER BY date ASC"
        )
        async with self._db_client.read() as cursor:
            await cursor.execute(sql, (instrument_key,))
            rows = await cursor.fetchall()
        return [
            InstrumentSplit(
                date=date.fromisoformat(row["date"]), ratio=Dezimal(row["ratio"])
            )
            for row in rows
        ]

    async def save_splits(self, instrument_key: str, splits: list) -> None:
        sql = (
            "INSERT INTO instrument_split_cache "
            "(id, instrument_key, date, ratio) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (instrument_key, date) DO UPDATE SET ratio = excluded.ratio"
        )
        async with self._db_client.tx(skip_last_update=True) as cursor:
            for split in splits:
                await cursor.execute(
                    sql,
                    (
                        str(uuid4()),
                        instrument_key,
                        split.date.isoformat(),
                        str(split.ratio),
                    ),
                )

    async def is_splits_checked(self, instrument_key: str) -> bool:
        sql = (
            "SELECT 1 FROM instrument_split_checked WHERE instrument_key = ? "
            "AND checked_at >= datetime('now', '-7 days')"
        )
        async with self._db_client.read() as cursor:
            await cursor.execute(sql, (instrument_key,))
            return await cursor.fetchone() is not None

    async def mark_splits_checked(self, instrument_key: str) -> None:
        sql = (
            "INSERT INTO instrument_split_checked (id, instrument_key, checked_at) "
            "VALUES (?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT (instrument_key) DO UPDATE SET checked_at = CURRENT_TIMESTAMP"
        )
        async with self._db_client.tx(skip_last_update=True) as cursor:
            await cursor.execute(sql, (str(uuid4()), instrument_key))

    async def get_empty_gap_days(
        self, instrument_key: str, from_date: date, to_date: date
    ) -> set[date]:
        sql = (
            "SELECT gap_date FROM instrument_price_gap "
            "WHERE instrument_key = ? AND gap_date >= ? AND gap_date <= ?"
        )
        async with self._db_client.read() as cursor:
            await cursor.execute(
                sql, (instrument_key, from_date.isoformat(), to_date.isoformat())
            )
            rows = await cursor.fetchall()
        return {date.fromisoformat(row["gap_date"]) for row in rows}

    async def mark_empty_gap_days(self, instrument_key: str, days: list[date]) -> None:
        if not days:
            return
        sql = (
            "INSERT INTO instrument_price_gap (id, instrument_key, gap_date) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT (instrument_key, gap_date) DO NOTHING"
        )
        async with self._db_client.tx(skip_last_update=True) as cursor:
            for day in days:
                await cursor.execute(
                    sql, (str(uuid4()), instrument_key, day.isoformat())
                )

    async def is_no_result(self, instrument_key: str) -> bool:
        sql = "SELECT 1 FROM instrument_no_result WHERE instrument_key = ?"
        async with self._db_client.read() as cursor:
            await cursor.execute(sql, (instrument_key,))
            return await cursor.fetchone() is not None

    async def mark_no_result(self, instrument_key: str) -> None:
        sql = (
            "INSERT INTO instrument_no_result (id, instrument_key, marked_at) "
            "VALUES (?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT (instrument_key) DO NOTHING"
        )
        async with self._db_client.tx(skip_last_update=True) as cursor:
            await cursor.execute(sql, (str(uuid4()), instrument_key))
