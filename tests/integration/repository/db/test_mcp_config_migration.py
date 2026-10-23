import sqlite3

import pytest
import pytest_asyncio

from domain.data_init import DatasourceInitContext
from domain.mcp import McpCategoryAccess, McpConfig, McpToolCategory
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v11.v0110_5_mcp_config import (
    V01105McpConfig,
)
from infrastructure.repository.db.versions.v0.v11.v0110_7_mcp_tool_categories import (
    V01107McpToolCategories,
)
from infrastructure.repository.mcp.mcp_config_repository import McpConfigRepository


@pytest_asyncio.fixture
async def client():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT)")
    connection.execute("INSERT INTO sys_config VALUES ('last_update', 'unchanged')")
    connection.commit()
    client = DBClient(connection)
    async with client.tx(skip_last_update=True) as cursor:
        context = DatasourceInitContext(config=None)
        await V01105McpConfig().upgrade(cursor, context)
        await cursor.execute(
            "INSERT INTO mcp_config VALUES (1, 1, 1, 'existing-token', '2026-10-23T00:00:00+00:00')"
        )
        await V01107McpToolCategories().upgrade(cursor, context)
    yield client
    connection.close()


@pytest.mark.asyncio
async def test_upgrade_preserves_existing_flags_and_token_with_default_categories(
    client,
):
    assert await McpConfigRepository(client).get() == McpConfig(
        enabled=True, read_only=False, token="existing-token", category_access={}
    )
    async with client.read() as cursor:
        await cursor.execute("PRAGMA table_info(mcp_config)")
        column = next(
            row for row in await cursor.fetchall() if row["name"] == "category_access"
        )
        assert column["notnull"] == 1
        assert column["dflt_value"] == "'{}'"


@pytest.mark.asyncio
async def test_empty_config_keeps_existing_defaults(client):
    async with client.tx(skip_last_update=True) as cursor:
        await cursor.execute("DELETE FROM mcp_config")
    assert await McpConfigRepository(client).get() == McpConfig()


@pytest.mark.asyncio
async def test_category_preferences_roundtrip_without_changing_financial_update(client):
    config = McpConfig(
        enabled=True,
        read_only=True,
        token="saved-token",
        category_access={
            McpToolCategory.POSITIONS: McpCategoryAccess(False, False),
            McpToolCategory.BUDGET: McpCategoryAccess(True, False),
        },
    )
    await McpConfigRepository(client).save(config)
    assert await McpConfigRepository(client).get() == config
    config.category_access[McpToolCategory.BUDGET] = McpCategoryAccess()
    await McpConfigRepository(client).save(config)
    assert await McpConfigRepository(client).get() == config
    async with client.read() as cursor:
        await cursor.execute("SELECT value FROM sys_config WHERE key = 'last_update'")
        assert (await cursor.fetchone())["value"] == "unchanged"
