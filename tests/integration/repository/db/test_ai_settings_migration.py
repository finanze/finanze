import json
import sqlite3
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from infrastructure.config.file_legacy_config_source import FileLegacyConfigSource
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v11.v0110_4_settings import (
    V01104Settings,
)
from infrastructure.repository.db.versions.v0.v12.v0120_4_ai_settings import (
    V01204AISettings,
)
from infrastructure.repository.settings.settings_repository import SettingsRepository

UPDATED_AT = "2026-10-01T10:00:00+02:00"
LABELING_EXTRAS = {
    "enabled": True,
    "autoRun": False,
    "minConfidence": 85,
    "maxPerRun": 150,
    "instructions": "Burgers are restaurants",
}


@pytest_asyncio.fixture
async def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    client = DBClient(conn)
    async with client.tx(skip_last_update=True) as cursor:
        await V01104Settings().upgrade(cursor, None)
    yield client, conn
    conn.close()


def _insert(conn, key: str, value: dict):
    conn.execute(
        'INSERT INTO settings ("key", value, updated_at) VALUES (?, ?, ?)',
        (key, json.dumps(value), UPDATED_AT),
    )
    conn.commit()


async def _migrate(client):
    async with client.tx(skip_last_update=True) as cursor:
        await V01204AISettings().upgrade(cursor, None)


def _rows(conn):
    return {
        row["key"]: (json.loads(row["value"]), row["updated_at"])
        for row in conn.execute('SELECT "key", value, updated_at FROM settings')
    }


class TestAISettingsMigration:
    @pytest.mark.asyncio
    async def test_moves_released_single_provider_to_shared_list(self, db, tmp_path):
        client, conn = db
        _insert(
            conn,
            "labeling",
            {
                "external": {
                    **LABELING_EXTRAS,
                    "provider": "OPENROUTER",
                    "model": "openai/gpt-5-mini",
                    "upstreamProvider": "openai",
                }
            },
        )

        await _migrate(client)

        rows = _rows(conn)
        assert rows["ai"] == (
            {
                "providers": [
                    {
                        "provider": "OPENROUTER",
                        "model": "openai/gpt-5-mini",
                        "upstreamProvider": "openai",
                    }
                ]
            },
            UPDATED_AT,
        )
        assert rows["labeling"] == (
            {"external": {**LABELING_EXTRAS, "providers": []}},
            UPDATED_AT,
        )

        repository = SettingsRepository(client, FileLegacyConfigSource())
        await repository.connect(MagicMock(path=tmp_path))
        settings = await repository.load()
        assert [entry.model for entry in settings.ai.providers] == ["openai/gpt-5-mini"]
        assert settings.labeling.external.providers == []
        assert settings.labeling.external.minConfidence == 85

    @pytest.mark.asyncio
    async def test_moves_priority_list_dropping_invalid_and_duplicates(self, db):
        client, conn = db
        _insert(
            conn,
            "labeling",
            {
                "external": {
                    **LABELING_EXTRAS,
                    "providers": [
                        {"provider": "OPENAI", "model": "gpt-6-luna"},
                        {"provider": "OPENAI", "model": "gpt-6-luna"},
                        {"provider": "OPENAI", "model": "  "},
                        "garbage",
                        {
                            "provider": "LOCAL_MODELS",
                            "model": " org/model:Q4 ",
                            "upstreamProvider": None,
                        },
                    ],
                }
            },
        )

        await _migrate(client)

        rows = _rows(conn)
        assert rows["ai"][0]["providers"] == [
            {"provider": "OPENAI", "model": "gpt-6-luna", "upstreamProvider": None},
            {
                "provider": "LOCAL_MODELS",
                "model": "org/model:Q4",
                "upstreamProvider": None,
            },
        ]
        assert rows["labeling"][0]["external"]["providers"] == []

    @pytest.mark.parametrize(
        "labeling",
        [
            {"external": {"enabled": False, "providers": []}},
            {"external": {"enabled": True}},
            {"external": "broken"},
            {},
        ],
    )
    @pytest.mark.asyncio
    async def test_nothing_to_move_keeps_rows_untouched(self, db, labeling):
        client, conn = db
        _insert(conn, "labeling", labeling)

        await _migrate(client)

        assert _rows(conn) == {"labeling": (labeling, UPDATED_AT)}

    @pytest.mark.asyncio
    async def test_existing_shared_list_wins(self, db):
        client, conn = db
        labeling = {"external": {"provider": "OPENAI", "model": "gpt-6-luna"}}
        ai = {"providers": [{"provider": "OPENROUTER", "model": "x/y"}]}
        _insert(conn, "labeling", labeling)
        _insert(conn, "ai", ai)

        await _migrate(client)

        assert _rows(conn) == {
            "labeling": (labeling, UPDATED_AT),
            "ai": (ai, UPDATED_AT),
        }

    @pytest.mark.asyncio
    async def test_without_settings_does_nothing(self, db):
        client, conn = db

        await _migrate(client)

        assert _rows(conn) == {}
