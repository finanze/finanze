import json
import sqlite3

import pytest
import pytest_asyncio

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v11.v0110_0_account_tx_labeling import (
    V01100AccountTxLabeling,
)

_SCHEMA = """
    CREATE TABLE account_transactions (
        id TEXT PRIMARY KEY,
        ref TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        type TEXT NOT NULL
    );
    CREATE TABLE external_integrations (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        status TEXT NOT NULL
    );
"""


@pytest_asyncio.fixture
async def setup():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(_SCHEMA)
    connection.executemany(
        "INSERT INTO account_transactions (id, ref, entity_id, type) VALUES (?, ?, ?, ?)",
        [
            ("tx-interest", "r1", "e1", "INTEREST"),
            ("tx-fee", "r2", "e1", "FEE"),
            ("tx-outflow", "r3", "e1", "OUTFLOW"),
        ],
    )
    connection.commit()
    client = DBClient(connection)
    async with client.tx(skip_last_update=True) as cursor:
        await V01100AccountTxLabeling().upgrade(
            cursor, DatasourceInitContext(config=None)
        )
    yield connection
    connection.close()


def _rule_labels_by_tx(connection) -> dict[str, tuple[str, str, str]]:
    rows = connection.execute(
        """
        SELECT atl.tx_id, l.key, atl.origin, r.conditions
        FROM account_transaction_labels atl
        JOIN labels l ON l.id = atl.label_id
        JOIN labeling_rules r ON r.id = atl.rule_id
        """
    ).fetchall()
    return {
        row["tx_id"]: (row["key"], row["origin"], row["conditions"]) for row in rows
    }


@pytest.mark.asyncio
async def test_base_labels_are_seeded_with_categories(setup):
    categories = {
        row["key"]: row["category"]
        for row in setup.execute("SELECT key, category FROM labels")
    }

    assert categories["interest"] == "INCOME"
    assert categories["salary"] == "INCOME"
    assert categories["groceries"] == "EXPENSE"
    assert {key for key, value in categories.items() if value == "EXCLUDED"} == {
        "internal_transfer",
        "savings_investment",
    }


@pytest.mark.asyncio
async def test_default_rules_label_existing_transactions(setup):
    labeled = _rule_labels_by_tx(setup)

    assert set(labeled) == {"tx-interest", "tx-fee"}
    key, origin, conditions = labeled["tx-interest"]
    assert (key, origin) == ("interest", "RULE")
    assert json.loads(conditions) == {"types": ["INTEREST"]}
    key, origin, conditions = labeled["tx-fee"]
    assert (key, origin) == ("bank_fees", "RULE")
    assert json.loads(conditions) == {"types": ["FEE"]}


@pytest.mark.asyncio
async def test_default_transfer_rule_is_seeded(setup):
    rows = setup.execute(
        """
        SELECT r.kind, r.enabled, r.conditions, l.key
        FROM labeling_rules r
        JOIN labeling_rule_labels rl ON rl.rule_id = r.id
        JOIN labels l ON l.id = rl.label_id
        """
    ).fetchall()
    by_kind = {}
    for row in rows:
        by_kind.setdefault(row["kind"], []).append(row)

    assert len(by_kind["MATCH"]) == 2
    assert len(by_kind["TRANSFER"]) == 1
    transfer = by_kind["TRANSFER"][0]
    assert transfer["enabled"] == 1
    assert json.loads(transfer["conditions"]) == {"max_days": 3}
    assert transfer["key"] == "internal_transfer"

    columns = {
        row["name"]
        for row in setup.execute("PRAGMA table_info(account_transfer_pairs)")
    }
    assert columns == {"tx_id", "paired_tx_id", "rule_id", "created_at"}


@pytest.mark.asyncio
async def test_account_transactions_get_movement_columns(setup):
    columns = {
        row["name"] for row in setup.execute("PRAGMA table_info(account_transactions)")
    }

    assert {"counterparty", "iban", "linked_tx", "labels_locked"} <= columns
