import sqlite3

import pytest

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v11.v0110_8_custom_ai_integration_name import (
    V01108CustomAIIntegrationName,
)


@pytest.mark.parametrize(
    ("initial_name", "expected_name"),
    [
        ("Custom endpoint", "Custom AI"),
        ("My custom provider", "My custom provider"),
    ],
)
@pytest.mark.asyncio
async def test_migration_renames_only_default_integration_name(
    initial_name, expected_name
):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE external_integrations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "INSERT INTO external_integrations VALUES (?, ?, ?, ?)",
        ("OPENAI_COMPATIBLE", initial_name, "AI_PROVIDER", "OFF"),
    )
    connection.commit()

    try:
        async with DBClient(connection).tx(skip_last_update=True) as cursor:
            await V01108CustomAIIntegrationName().upgrade(
                cursor, DatasourceInitContext(config=None)
            )

        async with DBClient(connection).read() as cursor:
            await cursor.execute(
                "SELECT name FROM external_integrations WHERE id = 'OPENAI_COMPATIBLE'"
            )
            assert (await cursor.fetchone())["name"] == expected_name
    finally:
        connection.close()
