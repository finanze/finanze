import json
import sqlite3

import pytest
import pytest_asyncio

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v11.v0110_0_account_tx_labeling import (
    V01100AccountTxLabeling,
)
from infrastructure.repository.db.versions.v0.v11.v0110_3_periodic_flow_budget_label import (
    V01103PeriodicFlowBudgetLabel,
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
    CREATE TABLE periodic_flows (
        id TEXT PRIMARY KEY
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


@pytest.mark.asyncio
async def test_label_subcategories_migrate_defaults_and_preserve_existing_categories(
    setup,
):
    setup.execute("UPDATE labels SET category = 'INCOME' WHERE key = 'shopping'")
    setup.execute(
        "UPDATE labels SET category = 'INCOME' WHERE key = 'internal_transfer'"
    )
    setup.execute(
        "INSERT INTO labels (id, name, category, created_at) VALUES (?, ?, ?, ?)",
        ("custom-label", "Custom expense", "EXPENSE", "2026-10-11T12:00:00+02:00"),
    )
    setup.commit()
    async with DBClient(setup).tx(skip_last_update=True) as cursor:
        await V01103PeriodicFlowBudgetLabel().upgrade(
            cursor, DatasourceInitContext(config=None)
        )
    assert "label_id" in {
        row["name"] for row in setup.execute("PRAGMA table_info(periodic_flows)")
    }
    assert "idx_periodic_flows_label_id" in {
        row["name"] for row in setup.execute("PRAGMA index_list(periodic_flows)")
    }
    labels = {
        row["key"] or row["id"]: (row["category"], row["subcategory"])
        for row in setup.execute("SELECT id, key, category, subcategory FROM labels")
    }

    assert labels["groceries"] == ("EXPENSE", "NEED")
    assert labels["restaurants"] == ("EXPENSE", "WANTS")
    assert labels["other_expense"] == ("EXPENSE", "WANTS")
    assert labels["salary"] == ("INCOME", "NONE")
    assert labels["shopping"] == ("INCOME", "NONE")
    assert labels["internal_transfer"] == ("EXCLUDED", "NONE")
    assert labels["savings_investment"] == ("EXCLUDED", "SAVINGS")
    assert labels["custom-label"] == ("EXPENSE", "NEED")
    assert {
        key for key, (_, subcategory) in labels.items() if subcategory == "SAVINGS"
    } == {"savings_investment"}
    for category, subcategory in labels.values():
        assert (
            subcategory
            in {
                "EXPENSE": {"NEED", "WANTS"},
                "INCOME": {"NONE"},
                "EXCLUDED": {"SAVINGS", "NONE"},
            }[category]
        )
