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
from infrastructure.repository.entity.queries import ExternalEntityQueries


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
                ExternalEntityQueries.UPSERT,
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
                ExternalEntityQueries.UPDATE_STATUS,
                (status.value, str(ee_id)),
            )

    def get_by_id(self, ee_id: UUID) -> Optional[ExternalEntity]:
        with self._db_client.read() as cursor:
            cursor.execute(
                ExternalEntityQueries.GET_BY_ID,
                (str(ee_id),),
            )
            row = cursor.fetchone()
            return _map_row(row) if row else None

    def get_by_entity_id(self, entity_id: UUID) -> Optional[ExternalEntity]:
        with self._db_client.read() as cursor:
            cursor.execute(
                ExternalEntityQueries.GET_BY_ENTITY_ID,
                (str(entity_id),),
            )
            row = cursor.fetchone()
            return _map_row(row) if row else None

    def delete_by_id(self, ee_id: UUID):
        with self._db_client.tx() as cursor:
            cursor.execute(
                ExternalEntityQueries.DELETE_BY_ID,
                (str(ee_id),),
            )

    def get_all(self) -> list[ExternalEntity]:
        with self._db_client.read() as cursor:
            cursor.execute(ExternalEntityQueries.GET_ALL)
            rows = cursor.fetchall()
            return [_map_row(row) for row in rows]
