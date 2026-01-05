from datetime import datetime
from uuid import UUID

from application.ports.last_fetches_port import LastFetchesPort
from domain.entity import Entity, Feature
from domain.fetch_record import FetchRecord
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.fetch.queries import LastFetchesQueries


class LastFetchesRepository(LastFetchesPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def get_by_entity_id(self, entity_id: UUID) -> list[FetchRecord]:
        with self._db_client.read() as cursor:
            cursor.execute(
                LastFetchesQueries.GET_BY_ENTITY_ID,
                (str(entity_id),),
            )
            rows = cursor.fetchall()
            return [
                FetchRecord(
                    entity_id=UUID(row["entity_id"]),
                    feature=Feature(row["feature"]),
                    date=datetime.fromisoformat(row["date"]),
                )
                for row in rows
            ]

    def get_grouped_by_entity(self, feature: Feature) -> dict[Entity, FetchRecord]:
        with self._db_client.read() as cursor:
            cursor.execute(
                LastFetchesQueries.GET_GROUPED_BY_ENTITY,
                (feature,),
            )
            rows = cursor.fetchall()

            return {
                Entity(
                    id=UUID(row["entity_id"]),
                    name=row["entity_name"],
                    natural_id=row["entity_natural_id"],
                    type=row["entity_type"],
                    origin=row["entity_origin"],
                    icon_url=row["icon_url"],
                ): FetchRecord(
                    entity_id=UUID(row["entity_id"]),
                    feature=Feature(row["feature"]),
                    date=datetime.fromisoformat(row["date"]),
                )
                for row in rows
            }

    def save(self, fetch_records: list[FetchRecord]):
        with self._db_client.tx() as cursor:
            for fetch_record in fetch_records:
                cursor.execute(
                    LastFetchesQueries.UPSERT,
                    (
                        str(fetch_record.entity_id),
                        fetch_record.feature.value,
                        fetch_record.date.isoformat(),
                    ),
                )
