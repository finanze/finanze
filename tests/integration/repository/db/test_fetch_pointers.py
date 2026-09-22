import sqlite3
from datetime import date
from uuid import uuid4

import pytest
import pytest_asyncio

from domain.data_init import DatasourceInitContext
from domain.fetch_pointer import FetchPointer
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v10.v0101_0_fetch_pointers import (
    V01010FetchPointers,
)
from infrastructure.repository.fetch.fetch_pointers_repository import (
    FetchPointersRepository,
)


@pytest_asyncio.fixture
async def setup():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        """
        CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT)
        """
    )
    connection.execute(
        """
        CREATE TABLE entities (id CHAR(36) PRIMARY KEY)
        """
    )
    connection.execute(
        """
        CREATE TABLE entity_accounts (
            id CHAR(36) PRIMARY KEY,
            entity_id CHAR(36) NOT NULL REFERENCES entities(id),
            created_at TIMESTAMP NOT NULL,
            deleted_at TIMESTAMP
        )
        """
    )
    client = DBClient(connection)
    async with client.tx() as cursor:
        await V01010FetchPointers().upgrade(cursor, DatasourceInitContext(config=None))
    yield client, connection
    connection.close()


@pytest.mark.asyncio
async def test_fetch_pointers_are_account_scoped_and_upserted(setup):
    client, connection = setup
    repository = FetchPointersRepository(client)
    entity_id = uuid4()
    first_account_id = uuid4()
    second_account_id = uuid4()
    connection.executemany(
        "INSERT INTO entities (id) VALUES (?)",
        [(str(entity_id),)],
    )
    connection.executemany(
        "INSERT INTO entity_accounts (id, entity_id, created_at) VALUES (?, ?, ?)",
        [
            (str(first_account_id), str(entity_id), "2025-01-01"),
            (str(second_account_id), str(entity_id), "2025-01-01"),
        ],
    )
    connection.commit()

    first_pointer = FetchPointer(
        entity_id=entity_id,
        entity_account_id=first_account_id,
        key="fund_orders:one",
        threshold=date(2025, 1, 1),
    )
    second_pointer = FetchPointer(
        entity_id=entity_id,
        entity_account_id=second_account_id,
        key="fund_orders:one",
        threshold=date(2025, 2, 1),
    )
    await repository.save([first_pointer, second_pointer])

    updated_pointer = FetchPointer(
        entity_id=entity_id,
        entity_account_id=first_account_id,
        key="fund_orders:one",
        threshold=date(2025, 3, 1),
    )
    await repository.save([updated_pointer])

    assert await repository.get_by_entity_account_id(first_account_id) == [
        updated_pointer
    ]
    assert await repository.get_by_entity_account_id(second_account_id) == [
        second_pointer
    ]

    await repository.delete_by_entity_account_id(first_account_id)

    assert await repository.get_by_entity_account_id(first_account_id) == []
    assert await repository.get_by_entity_account_id(second_account_id) == [
        second_pointer
    ]
