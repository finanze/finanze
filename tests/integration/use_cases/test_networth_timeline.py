import sqlite3
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio

from application.use_cases.get_networth_timeline import GetNetworthTimelineImpl
from domain.commodity import CommodityType, WeightUnit
from domain.dezimal import Dezimal
from domain.exchange_rate import HistoricMetalRates
from domain.networth_timeline import NetworthTimelineQuery
from domain.real_estate import RealEstateFlowSubtype
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.networth_timeline.networth_timeline_repository import (
    NetworthTimelineSQLRepository,
)

_SCHEMA = """
    CREATE TABLE global_positions (
        id CHAR(36) PRIMARY KEY,
        entity_id CHAR(36) NOT NULL,
        date DATETIME NOT NULL,
        source VARCHAR(255) NOT NULL,
        entity_account_id CHAR(36)
    );
    CREATE TABLE account_positions (id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), currency CHAR(3), total TEXT);
    CREATE TABLE stock_positions (id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), currency CHAR(3), market_value TEXT);
    CREATE TABLE fund_positions (id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), currency CHAR(3), market_value TEXT);
    CREATE TABLE deposit_positions (id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), currency CHAR(3), amount TEXT);
    CREATE TABLE factoring_positions (id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), currency CHAR(3), amount TEXT);
    CREATE TABLE real_estate_cf_positions (id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), currency CHAR(3), amount TEXT);
    CREATE TABLE crowdlending_positions (id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), currency CHAR(3), total TEXT);
    CREATE TABLE crypto_currency_positions (id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), currency CHAR(3), market_value TEXT);
    CREATE TABLE commodity_positions (
        id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), currency CHAR(3),
        market_value TEXT, type VARCHAR(32), amount TEXT, unit VARCHAR(32)
    );
    CREATE TABLE derivative_positions (id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), currency CHAR(3), market_value TEXT);
    CREATE TABLE card_positions (id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), currency CHAR(3), used TEXT);
    CREATE TABLE loan_positions (
        id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), currency CHAR(3),
        principal_outstanding TEXT, hash VARCHAR(64), creation DATE
    );
    CREATE TABLE credit_positions (id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), currency CHAR(3), drawn_amount TEXT);
    CREATE TABLE networth_timeline_points (
        date TEXT PRIMARY KEY, currency VARCHAR(10) NOT NULL, total TEXT NOT NULL, breakdown TEXT NOT NULL
    );
    CREATE TABLE networth_timeline_meta (
        id INTEGER PRIMARY KEY CHECK (id = 1), inputs_signature TEXT, last_computed_date TEXT
    );
    CREATE TABLE entity_accounts (
        id CHAR(36) PRIMARY KEY, entity_id CHAR(36) NOT NULL,
        created_at TIMESTAMP, deleted_at TIMESTAMP
    );
    CREATE TABLE virtual_data_imports (
        id CHAR(36) PRIMARY KEY, import_id CHAR(36) NOT NULL,
        global_position_id CHAR(36), source VARCHAR(255) NOT NULL,
        date TIMESTAMP NOT NULL, feature VARCHAR(255), entity_id CHAR(36)
    );
    CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT);
"""


def _insert_account(conn, entity_id, account_id, deleted_at=None):
    conn.execute(
        "INSERT INTO entity_accounts (id, entity_id, created_at, deleted_at) "
        "VALUES (?, ?, ?, ?)",
        (str(account_id), str(entity_id), "2025-01-01T00:00:00", deleted_at),
    )


def _insert_gp(conn, entity_id, day, source="REAL", account_id=None):
    gp_id = str(uuid4())
    conn.execute(
        "INSERT INTO global_positions (id, entity_id, date, source, entity_account_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            gp_id,
            str(entity_id),
            f"{day}T12:00:00",
            source,
            str(account_id) if account_id else None,
        ),
    )
    return gp_id


def _insert(conn, table, gp_id, value_col, value, currency="EUR", **extra):
    cols = ["id", "global_position_id", "currency", value_col]
    vals = [str(uuid4()), gp_id, currency, value]
    for k, v in extra.items():
        cols.append(k)
        vals.append(v)
    placeholders = ", ".join("?" for _ in cols)
    conn.execute(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})", vals
    )


def _insert_sheets_import(conn, import_id, gp_id, day, entity_id):
    conn.execute(
        "INSERT INTO virtual_data_imports "
        "(id, import_id, global_position_id, source, date, feature, entity_id) "
        "VALUES (?, ?, ?, 'SHEETS', ?, 'POSITION', ?)",
        (str(uuid4()), str(import_id), gp_id, f"{day}T12:00:00", str(entity_id)),
    )


def _insert_position_import(conn, import_id, gp_id, day, entity_id, source):
    conn.execute(
        "INSERT INTO virtual_data_imports "
        "(id, import_id, global_position_id, source, date, feature, entity_id) "
        "VALUES (?, ?, ?, ?, ?, 'POSITION', ?)",
        (
            str(uuid4()),
            str(import_id),
            gp_id,
            source,
            f"{day}T12:00:00",
            str(entity_id),
        ),
    )


@pytest_asyncio.fixture
async def setup():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(_SCHEMA)
    db_client = DBClient(conn)
    repository = NetworthTimelineSQLRepository(client=db_client)
    yield repository, conn
    conn.close()


def _use_case(repository, *, rates=None, real_estate=None, metal_rates=None):
    exchange = AsyncMock()
    exchange.get.return_value = rates if rates is not None else {}
    entity = AsyncMock()
    entity.get_disabled_entities.return_value = []
    real_estate_port = AsyncMock()
    real_estate_port.get_all.return_value = real_estate or []
    metal = AsyncMock()
    if metal_rates is None:
        metal.get_partial_historic_rates.return_value = None
    else:
        metal.get_partial_historic_rates.side_effect = lambda commodity, **kwargs: (
            metal_rates.get(commodity)
        )
    return GetNetworthTimelineImpl(
        repository, exchange, entity, real_estate_port, metal
    )


class TestNetworthTimelineRepositoryIntegration:
    @pytest.mark.asyncio
    async def test_end_to_end_compute_persist_and_read(self, setup):
        repository, conn = setup
        entity = uuid4()
        gp1 = _insert_gp(conn, entity, "2025-01-01")
        gp2 = _insert_gp(conn, entity, "2025-01-05")
        _insert(conn, "account_positions", gp1, "total", "1000")
        _insert(conn, "fund_positions", gp1, "market_value", "500", currency="USD")
        # A crypto holding with a NULL market value must be skipped (not crash)
        _insert(conn, "crypto_currency_positions", gp1, "market_value", None)
        _insert(conn, "account_positions", gp2, "total", "1200")
        _insert(conn, "fund_positions", gp2, "market_value", "500", currency="USD")
        conn.commit()

        rates = {"EUR": {"USD": Dezimal("1.25")}}
        use_case = _use_case(repository, rates=rates)

        result = await use_case.execute(NetworthTimelineQuery())

        by_day = {p.date.isoformat(): p for p in result.points}
        # 500 USD / 1.25 = 400 EUR
        assert by_day["2025-01-01"].breakdown["ACCOUNT"] == Dezimal(1000)
        assert by_day["2025-01-01"].breakdown["FUND"] == Dezimal(400)
        assert by_day["2025-01-01"].total == Dezimal(1400)
        assert by_day["2025-01-05"].total == Dezimal(1600)

        # Persisted to DB
        rows = conn.execute(
            "SELECT date, total FROM networth_timeline_points ORDER BY date"
        ).fetchall()
        assert [r["date"] for r in rows] == ["2025-01-01", "2025-01-05"]
        meta = conn.execute(
            "SELECT inputs_signature, last_computed_date FROM networth_timeline_meta WHERE id = 1"
        ).fetchone()
        assert meta["inputs_signature"] is not None
        assert meta["last_computed_date"] == "2025-01-05"

        # CRYPTO with null market value never appears in the breakdown
        assert "CRYPTO" not in by_day["2025-01-01"].breakdown

    @pytest.mark.asyncio
    async def test_no_calculation_reads_only(self, setup):
        repository, conn = setup
        result = await _use_case(repository).execute(
            NetworthTimelineQuery(no_calculation=True)
        )
        assert result.points == []
        # Nothing persisted
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM networth_timeline_points"
        ).fetchone()["c"]
        assert count == 0

    @pytest.mark.asyncio
    async def test_second_call_is_incremental(self, setup):
        repository, conn = setup
        entity = uuid4()
        gp1 = _insert_gp(conn, entity, "2025-02-01")
        _insert(conn, "account_positions", gp1, "total", "100")
        conn.commit()

        use_case = _use_case(repository)
        await use_case.execute(NetworthTimelineQuery())

        # Add a new day and recompute
        gp2 = _insert_gp(conn, entity, "2025-02-10")
        _insert(conn, "account_positions", gp2, "total", "300")
        conn.commit()

        result = await use_case.execute(NetworthTimelineQuery())
        by_day = {p.date.isoformat(): p for p in result.points}
        assert by_day["2025-02-01"].total == Dezimal(100)
        assert by_day["2025-02-10"].total == Dezimal(300)
        meta = conn.execute(
            "SELECT last_computed_date FROM networth_timeline_meta WHERE id = 1"
        ).fetchone()
        assert meta["last_computed_date"] == "2025-02-10"

    @pytest.mark.asyncio
    async def test_linked_mortgage_counted_once(self, setup):
        repository, conn = setup
        entity = uuid4()
        gp = _insert_gp(conn, entity, "2025-03-01")
        _insert(conn, "account_positions", gp, "total", "5000")
        _insert(
            conn,
            "loan_positions",
            gp,
            "principal_outstanding",
            "80000",
            hash="hashLINK",
            creation="2025-01-01",
        )
        _insert(
            conn,
            "loan_positions",
            gp,
            "principal_outstanding",
            "10000",
            hash="hashFREE",
            creation="2025-01-01",
        )
        conn.commit()

        real_estate = [
            SimpleNamespace(
                basic_info=SimpleNamespace(
                    name="Investment", is_residence=False, is_rented=True
                ),
                purchase_info=SimpleNamespace(
                    date=__import__("datetime").date(2025, 1, 1),
                    price=Dezimal("200000"),
                ),
                valuation_info=SimpleNamespace(
                    estimated_market_value=Dezimal("200000"), valuations=[]
                ),
                currency="EUR",
                flows=[
                    SimpleNamespace(
                        flow_subtype=RealEstateFlowSubtype.LOAN,
                        linked_loan_hash="hashLINK",
                        payload=SimpleNamespace(principal_outstanding=Dezimal("80000")),
                    )
                ],
            ),
            SimpleNamespace(
                basic_info=SimpleNamespace(
                    name="Home", is_residence=True, is_rented=False
                ),
                purchase_info=SimpleNamespace(
                    date=__import__("datetime").date(2025, 1, 1),
                    price=Dezimal("300000"),
                ),
                valuation_info=SimpleNamespace(
                    estimated_market_value=Dezimal("300000"), valuations=[]
                ),
                currency="EUR",
                flows=[],
            ),
        ]
        use_case = _use_case(repository, real_estate=real_estate)

        result = await use_case.execute(NetworthTimelineQuery())
        by_day = {p.date.isoformat(): p for p in result.points}
        point = by_day["2025-03-01"]
        # Unlinked loan only in LOAN bucket
        assert point.breakdown["LOAN"] == Dezimal(-10000)
        # Linked mortgage netted into investment real estate equity (200000 - 80000)
        assert point.breakdown["REAL_ESTATE"] == Dezimal(120000)
        # Residence property in its own bucket
        assert point.breakdown["REAL_ESTATE_RESIDENCE"] == Dezimal(300000)
        # Total = 5000 cash - 10000 unlinked loan + 120000 equity + 300000 residence
        assert point.total == Dezimal(415000)

    @pytest.mark.asyncio
    async def test_deleted_account_stops_contributing(self, setup):
        repository, conn = setup
        entity = uuid4()
        old_account = uuid4()
        new_account = uuid4()

        # An account deleted on 2025-04-10, then re-added as a new account.
        _insert_account(conn, entity, old_account, deleted_at="2025-04-10T00:00:00")
        _insert_account(conn, entity, new_account)

        old_gp = _insert_gp(conn, entity, "2025-04-01", account_id=old_account)
        _insert(conn, "account_positions", old_gp, "total", "1000000")
        new_gp = _insert_gp(conn, entity, "2025-04-15", account_id=new_account)
        _insert(conn, "account_positions", new_gp, "total", "1000000")
        conn.commit()

        result = await _use_case(repository).execute(NetworthTimelineQuery())
        by_day = {p.date.isoformat(): p for p in result.points}

        # While the old account is alive it contributes its balance.
        assert by_day["2025-04-01"].total == Dezimal(1000000)
        # On/after its deletion day it no longer contributes (gap until re-add).
        assert by_day["2025-04-10"].total == Dezimal(0)
        # The re-added account is counted once, not stacked on the deleted one.
        assert by_day["2025-04-15"].total == Dezimal(1000000)

    @pytest.mark.asyncio
    async def test_persisted_values_rounded_to_two_decimals(self, setup):
        repository, conn = setup
        entity = uuid4()
        gp = _insert_gp(conn, entity, "2025-07-01")
        _insert(conn, "account_positions", gp, "total", "100", currency="USD")
        conn.commit()

        rates = {"EUR": {"USD": Dezimal("3")}}  # 100 / 3 = 33.333...
        await _use_case(repository, rates=rates).execute(NetworthTimelineQuery())

        row = conn.execute(
            "SELECT total, breakdown FROM networth_timeline_points "
            "WHERE date = '2025-07-01'"
        ).fetchone()
        assert row["total"] == "33.33"
        assert '"ACCOUNT": "33.33"' in row["breakdown"]

    @pytest.mark.asyncio
    async def test_sheets_import_replaces_previous(self, setup):
        repository, conn = setup
        entity = uuid4()
        import1 = uuid4()
        import2 = uuid4()
        account_a = uuid4()
        account_b = uuid4()

        # First Sheets import declares two loans.
        gp_a = _insert_gp(
            conn, entity, "2025-09-11", source="SHEETS", account_id=account_a
        )
        _insert(
            conn,
            "loan_positions",
            gp_a,
            "principal_outstanding",
            "148500",
            hash="hashA",
            creation="2025-08-26",
        )
        _insert_sheets_import(conn, import1, gp_a, "2025-09-11", entity)
        gp_b1 = _insert_gp(
            conn, entity, "2025-09-11", source="SHEETS", account_id=account_b
        )
        _insert(
            conn,
            "loan_positions",
            gp_b1,
            "principal_outstanding",
            "12718",
            hash="hashB",
            creation="2025-06-23",
        )
        _insert_sheets_import(conn, import1, gp_b1, "2025-09-11", entity)

        # Second Sheets import drops the 148500 loan, keeps only the 12718 one.
        gp_b2 = _insert_gp(
            conn, entity, "2025-11-19", source="SHEETS", account_id=account_b
        )
        _insert(
            conn,
            "loan_positions",
            gp_b2,
            "principal_outstanding",
            "12718",
            hash="hashB",
            creation="2025-06-23",
        )
        _insert_sheets_import(conn, import2, gp_b2, "2025-11-19", entity)
        conn.commit()

        result = await _use_case(repository).execute(NetworthTimelineQuery())
        by_day = {p.date.isoformat(): p for p in result.points}

        # First import: both loans counted as debt.
        assert by_day["2025-09-11"].breakdown["LOAN"] == Dezimal(-161218)
        # Second import fully replaces the first → only the 12718 loan remains.
        assert by_day["2025-11-19"].breakdown["LOAN"] == Dezimal(-12718)

    @pytest.mark.asyncio
    async def test_manual_redeclaring_import_keeps_and_drops_holders(self, setup):
        # Manual imports fully re-declare the manual portfolio. An unchanged
        # position is re-referenced by later imports (kept, never duplicated);
        # a position omitted by a later import stops contributing from that day.
        repository, conn = setup
        entity = uuid4()
        import1 = uuid4()
        import2 = uuid4()
        import3 = uuid4()
        account_a = uuid4()
        account_b = uuid4()

        # First import: a deposit only.
        gp_dep = _insert_gp(
            conn, entity, "2026-01-30", source="MANUAL", account_id=account_a
        )
        _insert(conn, "deposit_positions", gp_dep, "amount", "2000")
        _insert_position_import(conn, import1, gp_dep, "2026-01-30", entity, "MANUAL")

        # Second import re-declares the deposit (re-reference) and adds factoring.
        gp_fac = _insert_gp(
            conn, entity, "2026-04-12", source="MANUAL", account_id=account_b
        )
        _insert(conn, "factoring_positions", gp_fac, "amount", "1100")
        _insert_position_import(conn, import2, gp_dep, "2026-04-12", entity, "MANUAL")
        _insert_position_import(conn, import2, gp_fac, "2026-04-12", entity, "MANUAL")

        # Third import drops the deposit, keeps only factoring.
        _insert_position_import(conn, import3, gp_fac, "2026-05-20", entity, "MANUAL")
        conn.commit()

        result = await _use_case(repository).execute(NetworthTimelineQuery())
        by_day = {p.date.isoformat(): p for p in result.points}

        # First import: deposit alone.
        assert by_day["2026-01-30"].total == Dezimal(2000)
        # Second import: deposit kept (not duplicated) + factoring added.
        assert by_day["2026-04-12"].breakdown["DEPOSIT"] == Dezimal(2000)
        assert by_day["2026-04-12"].breakdown["FACTORING"] == Dezimal(1100)
        assert by_day["2026-04-12"].total == Dezimal(3100)
        # Third import drops the deposit → only factoring remains.
        assert "DEPOSIT" not in by_day["2026-05-20"].breakdown
        assert by_day["2026-05-20"].breakdown["FACTORING"] == Dezimal(1100)
        assert by_day["2026-05-20"].total == Dezimal(1100)

    @pytest.mark.asyncio
    async def test_manual_not_double_counted_with_real(self, setup):
        # A bank account first entered manually and later connected as REAL must
        # not be counted twice: the REAL holder and the manual source are
        # independent, and the stale manual entry is replaced when the manual
        # import that drops it arrives.
        repository, conn = setup
        entity = uuid4()
        manual_import1 = uuid4()
        manual_import2 = uuid4()
        account = uuid4()
        _insert_account(conn, entity, account)

        # Manual fund entry, declared by the first manual import.
        gp_manual = _insert_gp(
            conn, entity, "2025-11-01", source="MANUAL", account_id=account
        )
        _insert(conn, "fund_positions", gp_manual, "market_value", "50000")
        _insert_position_import(
            conn, manual_import1, gp_manual, "2025-11-01", entity, "MANUAL"
        )

        # The account is later connected (REAL) and reports its real value.
        gp_real = _insert_gp(
            conn, entity, "2026-05-22", source="REAL", account_id=account
        )
        _insert(conn, "fund_positions", gp_real, "market_value", "73000")

        # A later manual import drops the now-real fund entry.
        gp_other = _insert_gp(
            conn, entity, "2026-06-01", source="MANUAL", account_id=None
        )
        _insert(conn, "deposit_positions", gp_other, "amount", "500")
        _insert_position_import(
            conn, manual_import2, gp_other, "2026-06-01", entity, "MANUAL"
        )
        conn.commit()

        result = await _use_case(repository).execute(NetworthTimelineQuery())
        by_day = {p.date.isoformat(): p for p in result.points}

        # While only the manual fund exists.
        assert by_day["2025-11-01"].breakdown["FUND"] == Dezimal(50000)
        # REAL fund arrives: manual import still declares it until replaced.
        assert by_day["2026-05-22"].breakdown["FUND"] == Dezimal(123000)
        # The newer manual import drops the manual fund → only the REAL fund and
        # the new manual deposit remain (no double counting of the fund).
        assert by_day["2026-06-01"].breakdown["FUND"] == Dezimal(73000)
        assert by_day["2026-06-01"].breakdown["DEPOSIT"] == Dezimal(500)

    @pytest.mark.asyncio
    async def test_commodity_revalued_daily_from_historic_rates(self, setup):
        repository, conn = setup
        entity = uuid4()
        gp = _insert_gp(conn, entity, "2025-06-15")
        _insert(
            conn,
            "commodity_positions",
            gp,
            "market_value",
            "1000",
            type="GOLD",
            amount="31.1034768",
            unit="GRAM",
        )
        conn.commit()

        historic = HistoricMetalRates(
            unit=WeightUnit.TROY_OUNCE,
            days=(date(2025, 6, 15), date(2025, 6, 20)),
            prices={"EUR": (Dezimal("2000"), Dezimal("2100"))},
        )
        use_case = _use_case(repository, metal_rates={CommodityType.GOLD: historic})

        result = await use_case.execute(NetworthTimelineQuery())

        by_day = {p.date.isoformat(): p for p in result.points}
        assert len(result.points) == 2
        # The stale stored market value (1000) is replaced by weight × price.
        assert by_day["2025-06-15"].breakdown["COMMODITY"] == Dezimal(2000)
        # The day without a snapshot gets a densified revalued point.
        assert by_day["2025-06-20"].breakdown["COMMODITY"] == Dezimal(2100)
