from datetime import date
from uuid import UUID

from application.ports.fetch_pointers_port import FetchPointersPort
from domain.fetch_pointer import FetchPointer
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.fetch.queries import FetchPointersQueries


def _map_row(row) -> FetchPointer:
    return FetchPointer(
        entity_id=UUID(row["entity_id"]),
        entity_account_id=UUID(row["entity_account_id"]),
        key=row["key"],
        threshold=date.fromisoformat(row["threshold"]),
    )


class FetchPointersRepository(FetchPointersPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def get_by_entity_account_id(
        self, entity_account_id: UUID
    ) -> list[FetchPointer]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                FetchPointersQueries.GET_BY_ENTITY_ACCOUNT_ID,
                (str(entity_account_id),),
            )
            rows = await cursor.fetchall()
            return [_map_row(row) for row in rows]

    async def save(self, fetch_pointers: list[FetchPointer]):
        if not fetch_pointers:
            return

        async with self._db_client.tx() as cursor:
            for fetch_pointer in fetch_pointers:
                await cursor.execute(
                    FetchPointersQueries.UPSERT,
                    (
                        str(fetch_pointer.entity_id),
                        str(fetch_pointer.entity_account_id),
                        fetch_pointer.key,
                        fetch_pointer.threshold.isoformat(),
                    ),
                )

    async def delete_by_entity_account_id(self, entity_account_id: UUID):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                FetchPointersQueries.DELETE_BY_ENTITY_ACCOUNT_ID,
                (str(entity_account_id),),
            )
