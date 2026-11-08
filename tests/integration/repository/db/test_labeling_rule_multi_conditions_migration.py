import json
import sqlite3
from uuid import uuid4

import pytest
import pytest_asyncio

from domain.data_init import DatasourceInitContext
from domain.labeling import LabelingRuleKind, TextMatchOperator
from domain.transactions import TxType
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v11.v0110_0_account_tx_labeling import (
    V01100AccountTxLabeling,
)
from infrastructure.repository.db.versions.v0.v12.v0120_3_labeling_rule_multi_conditions import (
    V01203LabelingRuleMultiConditions,
)
from infrastructure.repository.labeling.labeling_rule_repository import (
    LabelingRuleRepository,
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

TEXT_RULE_ID = str(uuid4())
REGEX_RULE_ID = str(uuid4())


async def _migrate(connection):
    async with DBClient(connection).tx(skip_last_update=True) as cursor:
        await V01203LabelingRuleMultiConditions().upgrade(
            cursor, DatasourceInitContext(config=None)
        )


@pytest_asyncio.fixture
async def setup():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(_SCHEMA)
    client = DBClient(connection)
    async with client.tx(skip_last_update=True) as cursor:
        await V01100AccountTxLabeling().upgrade(
            cursor, DatasourceInitContext(config=None)
        )
    connection.executemany(
        """
        INSERT INTO labeling_rules (id, name, enabled, kind, conditions, created_at, updated_at)
        VALUES (?, ?, TRUE, 'MATCH', ?, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
        """,
        [
            (
                TEXT_RULE_ID,
                "Supermarket",
                json.dumps(
                    {
                        "text": {
                            "value": "mercadona",
                            "operator": "CONTAINS",
                            "field": "NAME",
                        },
                        "min_amount": "10",
                    }
                ),
            ),
            (
                REGEX_RULE_ID,
                "Regex",
                json.dumps({"text": {"value": "^netflix", "operator": "REGEX"}}),
            ),
        ],
    )
    connection.commit()
    await _migrate(connection)
    yield connection
    connection.close()


def _conditions_by_id(connection) -> dict[str, list]:
    return {
        row["id"]: json.loads(row["conditions"])
        for row in connection.execute("SELECT id, conditions FROM labeling_rules")
    }


@pytest.mark.asyncio
async def test_conditions_are_wrapped_into_groups_and_text_values(setup):
    conditions = _conditions_by_id(setup)

    assert conditions[TEXT_RULE_ID] == [
        {
            "text": {"values": ["mercadona"], "operator": "CONTAINS", "field": "NAME"},
            "min_amount": "10",
        }
    ]
    assert conditions[REGEX_RULE_ID] == [
        {"text": {"values": ["^netflix"], "operator": "REGEX"}}
    ]
    seeded = [
        value
        for rule_id, value in conditions.items()
        if rule_id not in {TEXT_RULE_ID, REGEX_RULE_ID}
    ]
    assert sorted(seeded, key=json.dumps) == [
        [{"max_days": 3}],
        [{"types": ["FEE"]}],
        [{"types": ["INTEREST"]}],
    ]


@pytest.mark.asyncio
async def test_migration_is_idempotent(setup):
    before = _conditions_by_id(setup)
    await _migrate(setup)

    assert _conditions_by_id(setup) == before


@pytest.mark.asyncio
async def test_migrated_rules_are_readable_by_repository(setup):
    rules = {
        str(rule.id): rule
        for rule in await LabelingRuleRepository(DBClient(setup)).get_all()
    }

    text_rule = rules[TEXT_RULE_ID]
    assert len(text_rule.conditions) == 1
    assert text_rule.conditions[0].text.values == ["mercadona"]
    assert rules[REGEX_RULE_ID].conditions[0].text.operator == TextMatchOperator.REGEX

    transfer = next(
        rule for rule in rules.values() if rule.kind == LabelingRuleKind.TRANSFER
    )
    assert transfer.conditions[0].max_days == 3
    assert {
        tuple(rule.conditions[0].types)
        for rule in rules.values()
        if rule.kind == LabelingRuleKind.MATCH and rule.conditions[0].types
    } == {(TxType.INTEREST,), (TxType.FEE,)}
