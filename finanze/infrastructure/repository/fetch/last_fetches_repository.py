from datetime import datetime
from uuid import UUID

from application.ports.last_fetches_port import LastFetchesPort
from domain.entity import Entity, Feature
from domain.fetch_record import FetchRecord
from infrastructure.repository.db.client import DBClient


class LastFetchesRepository(LastFetchesPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def get_by_entity_id(self, entity_id: UUID) -> list[FetchRecord]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT entity_id, feature, date FROM last_fetches WHERE entity_id = ?",
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
                """SELECT lf.entity_id,
                          e.name       as entity_name,
                          e.natural_id as entity_natural_id,
                          e.type       as entity_type,
                          e.origin     as entity_origin,
                          lf.feature,
                          lf.date
                   FROM last_fetches lf
                            JOIN entities e ON lf.entity_id = e.id
                   WHERE feature = ?
                """,
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
                    """
                    INSERT OR REPLACE INTO last_fetches (entity_id, feature, date)
                    VALUES (?, ?, ?)
                    """,
                    (
                        str(fetch_record.entity_id),
                        fetch_record.feature.value,
                        fetch_record.date.isoformat(),
                    ),
                )
