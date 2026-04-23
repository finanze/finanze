import sqlite3
import uuid
from datetime import datetime, timezone

import pytest

from domain.entity_account import EntityAccount
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.entity_account.entity_account_repository import (
    EntityAccountRepository,
)

CREATE_TABLE_SQL = """
CREATE TABLE entity_accounts (
    id         CHAR(36) NOT NULL PRIMARY KEY,
    name       VARCHAR(100),
    entity_id  CHAR(36) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP
);
"""

ENTITY_ID_A = uuid.UUID("a0000000-0000-0000-0000-000000000001")
ENTITY_ID_B = uuid.UUID("b0000000-0000-0000-0000-000000000001")


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(CREATE_TABLE_SQL)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sys_config (key TEXT PRIMARY KEY, value TEXT)"
    )
    conn.commit()
    yield DBClient(connection=conn)
    conn.close()


def _account(
    entity_id=ENTITY_ID_A,
    name="My Account",
    account_id=None,
    created_at=None,
    deleted_at=None,
):
    return EntityAccount(
        id=account_id or uuid.uuid4(),
        entity_id=entity_id,
        name=name,
        created_at=created_at or datetime.now(timezone.utc),
        deleted_at=deleted_at,
    )


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_returns_account(self, db):
        repo = EntityAccountRepository(db)
        account = _account()

        result = await repo.create(account)

        assert result is account

    @pytest.mark.asyncio
    async def test_create_persists_account(self, db):
        repo = EntityAccountRepository(db)
        account = _account()

        await repo.create(account)
        fetched = await repo.get_by_id(account.id)

        assert fetched is not None
        assert fetched.id == account.id
        assert fetched.name == account.name
        assert fetched.entity_id == account.entity_id

    @pytest.mark.asyncio
    async def test_create_multiple_accounts(self, db):
        repo = EntityAccountRepository(db)
        acc1 = _account(name="Account 1")
        acc2 = _account(name="Account 2")

        await repo.create(acc1)
        await repo.create(acc2)

        results = await repo.get_by_entity_id(ENTITY_ID_A)
        assert len(results) == 2
        names = {r.name for r in results}
        assert names == {"Account 1", "Account 2"}


# ---------------------------------------------------------------------------
# get_by_entity_id
# ---------------------------------------------------------------------------


class TestGetByEntityId:
    @pytest.mark.asyncio
    async def test_returns_accounts_for_entity(self, db):
        repo = EntityAccountRepository(db)
        acc = _account(entity_id=ENTITY_ID_A)
        await repo.create(acc)

        results = await repo.get_by_entity_id(ENTITY_ID_A)

        assert len(results) == 1
        assert results[0].id == acc.id

    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_entity(self, db):
        repo = EntityAccountRepository(db)

        results = await repo.get_by_entity_id(uuid.uuid4())

        assert results == []

    @pytest.mark.asyncio
    async def test_excludes_soft_deleted(self, db):
        repo = EntityAccountRepository(db)
        acc = _account(entity_id=ENTITY_ID_A)
        await repo.create(acc)
        await repo.soft_delete(acc.id)

        results = await repo.get_by_entity_id(ENTITY_ID_A)

        assert results == []

    @pytest.mark.asyncio
    async def test_does_not_return_other_entity_accounts(self, db):
        repo = EntityAccountRepository(db)
        acc_a = _account(entity_id=ENTITY_ID_A, name="A")
        acc_b = _account(entity_id=ENTITY_ID_B, name="B")
        await repo.create(acc_a)
        await repo.create(acc_b)

        results = await repo.get_by_entity_id(ENTITY_ID_A)

        assert len(results) == 1
        assert results[0].entity_id == ENTITY_ID_A


# ---------------------------------------------------------------------------
# get_by_id
# ---------------------------------------------------------------------------


class TestGetById:
    @pytest.mark.asyncio
    async def test_returns_account(self, db):
        repo = EntityAccountRepository(db)
        acc = _account(name="Target")
        await repo.create(acc)

        result = await repo.get_by_id(acc.id)

        assert result is not None
        assert result.id == acc.id
        assert result.name == "Target"

    @pytest.mark.asyncio
    async def test_returns_none_for_missing(self, db):
        repo = EntityAccountRepository(db)

        result = await repo.get_by_id(uuid.uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_soft_deleted(self, db):
        repo = EntityAccountRepository(db)
        acc = _account()
        await repo.create(acc)
        await repo.soft_delete(acc.id)

        result = await repo.get_by_id(acc.id)

        assert result is None

    @pytest.mark.asyncio
    async def test_preserves_all_fields(self, db):
        repo = EntityAccountRepository(db)
        now = datetime.now(timezone.utc)
        acc = _account(
            entity_id=ENTITY_ID_B,
            name="Full Fields",
            created_at=now,
        )
        await repo.create(acc)

        result = await repo.get_by_id(acc.id)

        assert result is not None
        assert result.entity_id == ENTITY_ID_B
        assert result.name == "Full Fields"
        assert result.deleted_at is None


# ---------------------------------------------------------------------------
# get_by_ids
# ---------------------------------------------------------------------------


class TestGetByIds:
    @pytest.mark.asyncio
    async def test_returns_matching_accounts(self, db):
        repo = EntityAccountRepository(db)
        acc1 = _account(name="One")
        acc2 = _account(name="Two")
        await repo.create(acc1)
        await repo.create(acc2)

        results = await repo.get_by_ids([acc1.id, acc2.id])

        assert len(results) == 2
        ids = {r.id for r in results}
        assert ids == {acc1.id, acc2.id}

    @pytest.mark.asyncio
    async def test_empty_list_returns_empty(self, db):
        repo = EntityAccountRepository(db)

        results = await repo.get_by_ids([])

        assert results == []

    @pytest.mark.asyncio
    async def test_excludes_soft_deleted(self, db):
        repo = EntityAccountRepository(db)
        acc1 = _account(name="Keep")
        acc2 = _account(name="Delete")
        await repo.create(acc1)
        await repo.create(acc2)
        await repo.soft_delete(acc2.id)

        results = await repo.get_by_ids([acc1.id, acc2.id])

        assert len(results) == 1
        assert results[0].id == acc1.id

    @pytest.mark.asyncio
    async def test_unknown_ids_are_silently_ignored(self, db):
        repo = EntityAccountRepository(db)
        acc = _account()
        await repo.create(acc)

        results = await repo.get_by_ids([acc.id, uuid.uuid4()])

        assert len(results) == 1
        assert results[0].id == acc.id

    @pytest.mark.asyncio
    async def test_all_soft_deleted_returns_empty(self, db):
        repo = EntityAccountRepository(db)
        acc1 = _account(name="Del1")
        acc2 = _account(name="Del2")
        await repo.create(acc1)
        await repo.create(acc2)
        await repo.soft_delete(acc1.id)
        await repo.soft_delete(acc2.id)

        results = await repo.get_by_ids([acc1.id, acc2.id])

        assert results == []


# ---------------------------------------------------------------------------
# soft_delete
# ---------------------------------------------------------------------------


class TestSoftDelete:
    @pytest.mark.asyncio
    async def test_soft_delete_makes_account_invisible(self, db):
        repo = EntityAccountRepository(db)
        acc = _account()
        await repo.create(acc)

        await repo.soft_delete(acc.id)

        assert await repo.get_by_id(acc.id) is None

    @pytest.mark.asyncio
    async def test_soft_delete_does_not_affect_other_accounts(self, db):
        repo = EntityAccountRepository(db)
        acc1 = _account(name="Keep")
        acc2 = _account(name="Delete")
        await repo.create(acc1)
        await repo.create(acc2)

        await repo.soft_delete(acc2.id)

        assert await repo.get_by_id(acc1.id) is not None
        assert await repo.get_by_id(acc2.id) is None

    @pytest.mark.asyncio
    async def test_soft_delete_nonexistent_id_is_noop(self, db):
        repo = EntityAccountRepository(db)

        await repo.soft_delete(uuid.uuid4())  # should not raise


# ---------------------------------------------------------------------------
# soft_delete_by_entity_id
# ---------------------------------------------------------------------------


class TestSoftDeleteByEntityId:
    @pytest.mark.asyncio
    async def test_deletes_all_accounts_for_entity(self, db):
        repo = EntityAccountRepository(db)
        acc1 = _account(entity_id=ENTITY_ID_A, name="A1")
        acc2 = _account(entity_id=ENTITY_ID_A, name="A2")
        await repo.create(acc1)
        await repo.create(acc2)

        await repo.soft_delete_by_entity_id(ENTITY_ID_A)

        results = await repo.get_by_entity_id(ENTITY_ID_A)
        assert results == []

    @pytest.mark.asyncio
    async def test_does_not_affect_other_entity(self, db):
        repo = EntityAccountRepository(db)
        acc_a = _account(entity_id=ENTITY_ID_A, name="A")
        acc_b = _account(entity_id=ENTITY_ID_B, name="B")
        await repo.create(acc_a)
        await repo.create(acc_b)

        await repo.soft_delete_by_entity_id(ENTITY_ID_A)

        assert await repo.get_by_id(acc_a.id) is None
        assert await repo.get_by_id(acc_b.id) is not None

    @pytest.mark.asyncio
    async def test_skips_already_deleted(self, db):
        repo = EntityAccountRepository(db)
        acc1 = _account(entity_id=ENTITY_ID_A, name="Already deleted")
        acc2 = _account(entity_id=ENTITY_ID_A, name="Active")
        await repo.create(acc1)
        await repo.create(acc2)
        await repo.soft_delete(acc1.id)

        await repo.soft_delete_by_entity_id(ENTITY_ID_A)

        # Both should now be invisible
        results = await repo.get_by_entity_id(ENTITY_ID_A)
        assert results == []

    @pytest.mark.asyncio
    async def test_nonexistent_entity_is_noop(self, db):
        repo = EntityAccountRepository(db)

        await repo.soft_delete_by_entity_id(uuid.uuid4())  # should not raise
