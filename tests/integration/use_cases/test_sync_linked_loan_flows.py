import sqlite3
from datetime import date
from uuid import uuid4

import pytest
import pytest_asyncio

from domain.dezimal import Dezimal
from domain.global_position import (
    InstallmentFrequency,
    InterestType,
    Loan,
    LoanType,
)
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.real_estate.real_estate_repository import (
    RealEstateRepository,
)

_SCHEMA = """
    CREATE TABLE sys_config ("key" VARCHAR(128) PRIMARY KEY, value TEXT);

    CREATE TABLE periodic_flows (
        id        CHAR(36) PRIMARY KEY,
        name      TEXT        NOT NULL,
        amount    TEXT        NOT NULL,
        currency  CHAR(3)     NOT NULL,
        flow_type VARCHAR(16) NOT NULL,
        frequency VARCHAR(32) NOT NULL,
        category  TEXT,
        enabled   BOOLEAN     NOT NULL DEFAULT TRUE,
        since     DATE        NOT NULL,
        until     DATE
    );

    CREATE TABLE real_estate_flows (
        real_estate_id   CHAR(36)    NOT NULL,
        periodic_flow_id CHAR(36)    NOT NULL,
        flow_subtype     VARCHAR(16) NOT NULL,
        description      TEXT        NOT NULL,
        payload          JSON        NOT NULL,
        extra_reference  VARCHAR(255),
        PRIMARY KEY (real_estate_id, periodic_flow_id)
    );
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_pf(
    conn, pf_id, amount="500", freq="MONTHLY", since="2020-01-15", until="2050-01-15"
):
    conn.execute(
        "INSERT INTO periodic_flows (id, name, amount, currency, flow_type, frequency, enabled, since, until) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (str(pf_id), "Loan flow", amount, "EUR", "EXPENSE", freq, 1, since, until),
    )
    conn.commit()


def _insert_ref(conn, re_id, pf_id, extra_reference):
    conn.execute(
        "INSERT INTO real_estate_flows (real_estate_id, periodic_flow_id, flow_subtype, description, payload, extra_reference) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (str(re_id), str(pf_id), "LOAN", "Mortgage", "{}", extra_reference),
    )
    conn.commit()


def _read_pf(conn, pf_id):
    row = conn.execute(
        "SELECT amount, frequency, since, until FROM periodic_flows WHERE id = ?",
        (str(pf_id),),
    ).fetchone()
    return dict(row) if row else None


def _make_loan(
    hash_val="",
    installment=Dezimal(500),
    freq=InstallmentFrequency.MONTHLY,
    creation=date(2020, 1, 15),
    maturity=date(2050, 1, 15),
):
    loan = Loan(
        id=uuid4(),
        type=LoanType.MORTGAGE,
        currency="EUR",
        current_installment=installment,
        interest_rate=Dezimal("0.03"),
        loan_amount=Dezimal(100000),
        creation=creation,
        maturity=maturity,
        principal_outstanding=Dezimal(80000),
        interest_type=InterestType.FIXED,
        installment_frequency=freq,
    )
    loan.hash = hash_val
    return loan


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def setup():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(_SCHEMA)

    db_client = DBClient(conn)
    repository = RealEstateRepository(client=db_client)
    yield repository, conn
    conn.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSyncLinkedLoanFlows:
    @pytest.mark.asyncio
    async def test_single_matching_flow_updated(self, setup):
        repo, conn = setup
        pf_id = uuid4()
        re_id = uuid4()

        _insert_pf(
            conn,
            pf_id,
            amount="500",
            freq="MONTHLY",
            since="2020-01-15",
            until="2050-01-15",
        )
        _insert_ref(conn, re_id, pf_id, extra_reference="hash1")

        loan = _make_loan(hash_val="hash1", installment=Dezimal(510))

        await repo.sync_linked_loan_flows(loan)

        row = _read_pf(conn, pf_id)
        assert row["amount"] == "510"
        assert row["frequency"] == "MONTHLY"
        assert row["since"] == "2020-01-15"
        assert row["until"] == "2050-01-15"

    @pytest.mark.asyncio
    async def test_multiple_matching_flows_all_updated(self, setup):
        repo, conn = setup
        pf_id1, pf_id2 = uuid4(), uuid4()
        re_id1, re_id2 = uuid4(), uuid4()

        _insert_pf(conn, pf_id1, amount="400")
        _insert_pf(conn, pf_id2, amount="450")
        _insert_ref(conn, re_id1, pf_id1, extra_reference="shared_hash")
        _insert_ref(conn, re_id2, pf_id2, extra_reference="shared_hash")

        loan = _make_loan(hash_val="shared_hash", installment=Dezimal(600))

        await repo.sync_linked_loan_flows(loan)

        assert _read_pf(conn, pf_id1)["amount"] == "600"
        assert _read_pf(conn, pf_id2)["amount"] == "600"

    @pytest.mark.asyncio
    async def test_no_matching_flows_no_error(self, setup):
        repo, conn = setup
        pf_id = uuid4()

        _insert_pf(conn, pf_id, amount="500")
        _insert_ref(conn, uuid4(), pf_id, extra_reference="other_hash")

        loan = _make_loan(hash_val="unmatched")

        await repo.sync_linked_loan_flows(loan)

        assert _read_pf(conn, pf_id)["amount"] == "500"

    @pytest.mark.asyncio
    async def test_empty_hash_early_return(self, setup):
        repo, conn = setup
        pf_id = uuid4()

        _insert_pf(conn, pf_id, amount="500")
        _insert_ref(conn, uuid4(), pf_id, extra_reference="some_hash")

        loan = _make_loan(hash_val="")

        await repo.sync_linked_loan_flows(loan)

        assert _read_pf(conn, pf_id)["amount"] == "500"

    @pytest.mark.asyncio
    async def test_frequency_mapping_quarterly(self, setup):
        repo, conn = setup
        pf_id = uuid4()

        _insert_pf(conn, pf_id, freq="MONTHLY")
        _insert_ref(conn, uuid4(), pf_id, extra_reference="q_hash")

        loan = _make_loan(hash_val="q_hash", freq=InstallmentFrequency.QUARTERLY)

        await repo.sync_linked_loan_flows(loan)

        assert _read_pf(conn, pf_id)["frequency"] == "QUARTERLY"

    @pytest.mark.asyncio
    async def test_frequency_mapping_semiannual(self, setup):
        repo, conn = setup
        pf_id = uuid4()

        _insert_pf(conn, pf_id, freq="MONTHLY")
        _insert_ref(conn, uuid4(), pf_id, extra_reference="s_hash")

        loan = _make_loan(hash_val="s_hash", freq=InstallmentFrequency.SEMIANNUAL)

        await repo.sync_linked_loan_flows(loan)

        assert _read_pf(conn, pf_id)["frequency"] == "SEMIANNUALLY"

    @pytest.mark.asyncio
    async def test_unlinked_flows_not_affected(self, setup):
        repo, conn = setup
        pf_linked = uuid4()
        pf_unlinked = uuid4()

        _insert_pf(conn, pf_linked, amount="500")
        _insert_pf(conn, pf_unlinked, amount="300")
        _insert_ref(conn, uuid4(), pf_linked, extra_reference="target_hash")
        _insert_ref(conn, uuid4(), pf_unlinked, extra_reference="other_hash")

        loan = _make_loan(hash_val="target_hash", installment=Dezimal(600))

        await repo.sync_linked_loan_flows(loan)

        assert _read_pf(conn, pf_linked)["amount"] == "600"
        assert _read_pf(conn, pf_unlinked)["amount"] == "300"

    @pytest.mark.asyncio
    async def test_dates_updated_from_loan(self, setup):
        repo, conn = setup
        pf_id = uuid4()

        _insert_pf(conn, pf_id, since="2019-01-01", until="2040-01-01")
        _insert_ref(conn, uuid4(), pf_id, extra_reference="date_hash")

        loan = _make_loan(
            hash_val="date_hash",
            creation=date(2020, 6, 15),
            maturity=date(2045, 6, 15),
        )

        await repo.sync_linked_loan_flows(loan)

        row = _read_pf(conn, pf_id)
        assert row["since"] == "2020-06-15"
        assert row["until"] == "2045-06-15"
