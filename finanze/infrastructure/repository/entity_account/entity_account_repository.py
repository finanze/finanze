from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from application.ports.entity_account_port import EntityAccountPort
from domain.entity_account import EntityAccount
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.entity_account.queries import EntityAccountQueries


class EntityAccountRepository(EntityAccountPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def create(self, account: EntityAccount) -> EntityAccount:
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                EntityAccountQueries.INSERT,
                (
                    str(account.id),
                    account.name,
                    str(account.entity_id),
                    account.created_at.isoformat(),
                ),
            )
        return account

    async def get_by_entity_id(self, entity_id: UUID) -> list[EntityAccount]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                EntityAccountQueries.GET_BY_ENTITY_ID,
                (str(entity_id),),
            )
            rows = await cursor.fetchall()
            return [self._map_row(row) for row in rows]

    async def get_by_id(self, account_id: UUID) -> Optional[EntityAccount]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                EntityAccountQueries.GET_BY_ID,
                (str(account_id),),
            )
            row = await cursor.fetchone()
            if row:
                return self._map_row(row)
            return None

    async def soft_delete(self, account_id: UUID):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                EntityAccountQueries.SOFT_DELETE,
                (datetime.now(timezone.utc).isoformat(), str(account_id)),
            )

    async def soft_delete_by_entity_id(self, entity_id: UUID):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                EntityAccountQueries.SOFT_DELETE_BY_ENTITY_ID,
                (datetime.now(timezone.utc).isoformat(), str(entity_id)),
            )

    @staticmethod
    def _map_row(row) -> EntityAccount:
        return EntityAccount(
            id=UUID(row["id"]),
            name=row["name"],
            entity_id=UUID(row["entity_id"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            deleted_at=(
                datetime.fromisoformat(row["deleted_at"]) if row["deleted_at"] else None
            ),
        )
