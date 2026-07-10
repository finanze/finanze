import sqlite3
from uuid import uuid4

import pytest
import pytest_asyncio

from domain.data_init import DatasourceInitContext
from domain.global_position import compute_loan_hash
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v09.v090_1_recompute_loan_hashes import (
    V0901RecomputeLoanHashes,
)

_SCHEMA = """
    CREATE TABLE global_positions (
        id CHAR(36) PRIMARY KEY,
        entity_id CHAR(36) NOT NULL,
        date DATETIME NOT NULL,
        source VARCHAR(255) NOT NULL,
        entity_account_id CHAR(36)
    );
    CREATE TABLE loan_positions (
        id CHAR(36) PRIMARY KEY,
        global_position_id CHAR(36),
        currency CHAR(3),
        loan_amount TEXT,
        principal_outstanding TEXT,
        creation DATE,
        hash VARCHAR(64)
    );
    CREATE TABLE real_estate_flows (
        id CHAR(36) PRIMARY KEY,
        extra_reference VARCHAR(255)
    );
    CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT);
"""


def _insert_gp(conn, entity_id):
    gp_id = str(uuid4())
    conn.execute(
        "INSERT INTO global_positions (id, entity_id, date, source) "
        "VALUES (?, ?, ?, 'REAL')",
        (gp_id, str(entity_id), "2025-01-01T12:00:00"),
    )
    return gp_id


def _insert_loan(conn, gp_id, loan_amount, creation, hash_value):
    conn.execute(
        "INSERT INTO loan_positions "
        "(id, global_position_id, currency, loan_amount, principal_outstanding, creation, hash) "
        "VALUES (?, ?, 'EUR', ?, ?, ?, ?)",
        (str(uuid4()), gp_id, loan_amount, loan_amount, creation, hash_value),
    )


def _insert_flow(conn, extra_reference):
    flow_id = str(uuid4())
    conn.execute(
        "INSERT INTO real_estate_flows (id, extra_reference) VALUES (?, ?)",
        (flow_id, extra_reference),
    )
    return flow_id


@pytest_asyncio.fixture
async def setup():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(_SCHEMA)
    db_client = DBClient(conn)
    yield db_client, conn
    conn.close()


def _bad_hash(entity_id, loan_amount, creation):
    raw = f"{entity_id}|{loan_amount}|{creation}"
    import hashlib

    return hashlib.shake_128(raw.encode()).hexdigest(16)


class TestRecomputeLoanHashesMigration:
    @pytest.mark.asyncio
    async def test_unifies_hashes_and_remaps_real_estate_flow_references(self, setup):
        db_client, conn = setup
        entity_id = uuid4()
        creation = "2025-01-01"

        # Same loan recorded with different textual amounts produced different
        # (wrong) hashes under the old text-based scheme.
        gp1 = _insert_gp(conn, entity_id)
        gp2 = _insert_gp(conn, entity_id)
        bad_hash_1 = _bad_hash(entity_id, "1000.0", creation)
        bad_hash_2 = _bad_hash(entity_id, "1000.00", creation)
        _insert_loan(conn, gp1, "1000.0", creation, bad_hash_1)
        _insert_loan(conn, gp2, "1000.00", creation, bad_hash_2)

        # A real estate flow linked to one of the stale hashes.
        flow_id = _insert_flow(conn, bad_hash_1)
        conn.commit()

        expected_hash = compute_loan_hash(str(entity_id), "1000.0", creation)
        assert bad_hash_1 != expected_hash

        migration = V0901RecomputeLoanHashes()
        async with db_client.tx() as cursor:
            await migration.upgrade(cursor, DatasourceInitContext(config=None))

        hashes = {
            row["hash"]
            for row in conn.execute("SELECT hash FROM loan_positions").fetchall()
        }
        assert hashes == {expected_hash}

        flow_ref = conn.execute(
            "SELECT extra_reference FROM real_estate_flows WHERE id = ?", (flow_id,)
        ).fetchone()["extra_reference"]
        assert flow_ref == expected_hash

    @pytest.mark.asyncio
    async def test_leaves_unlinked_flows_untouched(self, setup):
        db_client, conn = setup
        entity_id = uuid4()
        creation = "2025-02-01"

        gp = _insert_gp(conn, entity_id)
        bad_hash = _bad_hash(entity_id, "5000.0", creation)
        _insert_loan(conn, gp, "5000.0", creation, bad_hash)

        # A flow referencing an unrelated hash must not be modified.
        flow_id = _insert_flow(conn, "unrelated_reference")
        conn.commit()

        migration = V0901RecomputeLoanHashes()
        async with db_client.tx() as cursor:
            await migration.upgrade(cursor, DatasourceInitContext(config=None))

        flow_ref = conn.execute(
            "SELECT extra_reference FROM real_estate_flows WHERE id = ?", (flow_id,)
        ).fetchone()["extra_reference"]
        assert flow_ref == "unrelated_reference"
