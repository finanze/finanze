from datetime import datetime
from typing import Optional
from uuid import uuid4

from application.ports.tracked_updates_port import TrackedUpdatesPort
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.tracked_updates.queries import (
    TrackedUpdatesQueries,
)


class TrackedUpdatesRepository(TrackedUpdatesPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def get_last_executed(self, use_case_name: str) -> Optional[datetime]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                TrackedUpdatesQueries.GET_BY_USE_CASE,
                (use_case_name,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return datetime.fromisoformat(row["last_executed_at"])

    async def update_last_executed(
        self, use_case_name: str, executed_at: datetime
    ) -> None:
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                TrackedUpdatesQueries.UPSERT,
                (str(uuid4()), use_case_name, executed_at.isoformat()),
            )
