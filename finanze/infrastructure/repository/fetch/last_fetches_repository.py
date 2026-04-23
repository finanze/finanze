from datetime import datetime
from uuid import UUID, uuid4

from application.ports.last_fetches_port import LastFetchesPort
from domain.entity import Feature
from domain.fetch_record import FetchRecord
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.fetch.queries import LastFetchesQueries


def _map_row(row) -> FetchRecord:
    entity_account_id_raw = row["entity_account_id"]
    return FetchRecord(
        entity_id=UUID(row["entity_id"]),
        feature=Feature(row["feature"]),
        date=datetime.fromisoformat(row["date"]),
        entity_account_id=UUID(entity_account_id_raw)
        if entity_account_id_raw
        else None,
    )


class LastFetchesRepository(LastFetchesPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def get_by_entity_id(self, entity_id: UUID) -> list[FetchRecord]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                LastFetchesQueries.GET_BY_ENTITY_ID,
                (str(entity_id),),
            )
            rows = await cursor.fetchall()
            return [_map_row(row) for row in rows]

    async def get_by_entity_account_id(
        self, entity_account_id: UUID
    ) -> list[FetchRecord]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                LastFetchesQueries.GET_BY_ENTITY_ACCOUNT_ID,
                (str(entity_account_id),),
            )
            rows = await cursor.fetchall()
            return [_map_row(row) for row in rows]

    async def save(self, fetch_records: list[FetchRecord]):
        async with self._db_client.tx() as cursor:
            for fetch_record in fetch_records:
                await cursor.execute(
                    LastFetchesQueries.UPSERT,
                    (
                        str(uuid4()),
                        str(fetch_record.entity_id),
                        fetch_record.feature.value,
                        fetch_record.date.isoformat(),
                        str(fetch_record.entity_account_id)
                        if fetch_record.entity_account_id
                        else None,
                    ),
                )
