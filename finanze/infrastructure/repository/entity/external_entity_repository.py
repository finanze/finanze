import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from application.ports.external_entity_port import (
    ExternalEntityPort,
)
from domain.external_entity import (
    ExternalEntity,
    ExternalEntityStatus,
)
from domain.external_integration import ExternalIntegrationId
from infrastructure.repository.db.client import DBClient


def _map_row(row) -> ExternalEntity:
    return ExternalEntity(
        id=UUID(row["id"]),
        entity_id=UUID(row["entity_id"]),
        status=ExternalEntityStatus(row["status"]),
        provider=ExternalIntegrationId(row["provider"]),
        date=datetime.fromisoformat(row["date"]),
        provider_instance_id=row["provider_instance_id"],
        payload=json.loads(row["payload"]) if row["payload"] else None,
    )


class ExternalEntityRepository(ExternalEntityPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def upsert(self, ee: ExternalEntity):
        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                INSERT INTO external_entities
                    (id, entity_id, status, provider, date, provider_instance_id, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT
                    (id)
                DO UPDATE SET
                    status = excluded.status,
                    provider_instance_id = excluded.provider_instance_id,
                    date = excluded.date,
                    payload = excluded.payload
                """,
                (
                    str(ee.id),
                    str(ee.entity_id),
                    ee.status.value,
                    ee.provider.value,
                    ee.date.isoformat(),
                    ee.provider_instance_id,
                    json.dumps(ee.payload) if ee.payload is not None else None,
                ),
            )

    def update_status(self, ee_id: UUID, status: ExternalEntityStatus):
        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                UPDATE external_entities
                SET status = ?
                WHERE id = ?
                """,
                (status.value, str(ee_id)),
            )

    def get_by_id(self, ee_id: UUID) -> Optional[ExternalEntity]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM external_entities WHERE id = ?",
                (str(ee_id),),
            )
            row = cursor.fetchone()
            return _map_row(row) if row else None

    def get_by_entity_id(self, entity_id: UUID) -> Optional[ExternalEntity]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM external_entities WHERE entity_id = ?",
                (str(entity_id),),
            )
            row = cursor.fetchone()
            return _map_row(row) if row else None

    def delete_by_id(self, ee_id: UUID):
        with self._db_client.tx() as cursor:
            cursor.execute(
                "DELETE FROM external_entities WHERE id = ?",
                (str(ee_id),),
            )
