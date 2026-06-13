import sqlite3
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from dateutil.tz import tzlocal

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.versions.v0.v09.v090_2_tracked_updates import (
    V0902TrackedUpdates,
)
from infrastructure.repository.tracked_updates.tracked_updates_repository import (
    TrackedUpdatesRepository,
)


@pytest_asyncio.fixture
async def setup():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT)")
    db_client = DBClient(conn)
    migration = V0902TrackedUpdates()
    async with db_client.tx() as cursor:
        await migration.upgrade(cursor, DatasourceInitContext(config=None))
    yield db_client, conn
    conn.close()


class TestTrackedUpdatesRepository:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_record(self, setup):
        db_client, _ = setup
        repo = TrackedUpdatesRepository(client=db_client)

        assert await repo.get_last_executed("TRACKED_QUOTES") is None

    @pytest.mark.asyncio
    async def test_records_and_reads_back(self, setup):
        db_client, _ = setup
        repo = TrackedUpdatesRepository(client=db_client)
        executed_at = datetime.now(tzlocal())

        await repo.update_last_executed("TRACKED_QUOTES", executed_at)

        stored = await repo.get_last_executed("TRACKED_QUOTES")
        assert stored == executed_at

    @pytest.mark.asyncio
    async def test_upsert_overwrites_previous_value(self, setup):
        db_client, conn = setup
        repo = TrackedUpdatesRepository(client=db_client)
        first = datetime.now(tzlocal()) - timedelta(hours=10)
        second = datetime.now(tzlocal())

        await repo.update_last_executed("TRACKED_LOANS", first)
        await repo.update_last_executed("TRACKED_LOANS", second)

        stored = await repo.get_last_executed("TRACKED_LOANS")
        assert stored == second

        count = conn.execute(
            "SELECT COUNT(*) AS c FROM tracked_updates "
            "WHERE use_case_name = 'TRACKED_LOANS'"
        ).fetchone()["c"]
        assert count == 1

    @pytest.mark.asyncio
    async def test_use_cases_tracked_independently(self, setup):
        db_client, _ = setup
        repo = TrackedUpdatesRepository(client=db_client)
        quotes_at = datetime.now(tzlocal()) - timedelta(hours=2)
        loans_at = datetime.now(tzlocal())

        await repo.update_last_executed("TRACKED_QUOTES", quotes_at)
        await repo.update_last_executed("TRACKED_LOANS", loans_at)

        assert await repo.get_last_executed("TRACKED_QUOTES") == quotes_at
        assert await repo.get_last_executed("TRACKED_LOANS") == loans_at
