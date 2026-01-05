from typing import Optional
from uuid import UUID

from application.ports.entity_port import EntityPort
from domain.entity import Entity
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.entity.queries import EntityQueries


def _map_entity(row) -> Entity:
    return Entity(
        id=UUID(row["id"]),
        name=row["name"],
        natural_id=row["natural_id"],
        type=row["type"],
        origin=row["origin"],
        icon_url=row["icon_url"],
    )


class EntitySQLRepository(EntityPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def insert(self, entity: Entity):
        with self._db_client.tx() as cursor:
            cursor.execute(
                EntityQueries.INSERT,
                (
                    str(entity.id),
                    entity.name,
                    entity.natural_id,
                    entity.type,
                    entity.origin,
                    entity.icon_url,
                ),
            )

    def update(self, entity: Entity):
        with self._db_client.tx() as cursor:
            cursor.execute(
                EntityQueries.UPDATE,
                (
                    entity.name,
                    entity.natural_id,
                    entity.type,
                    entity.origin,
                    entity.icon_url,
                    str(entity.id),
                ),
            )

    def get_by_id(self, entity_id: UUID) -> Optional[Entity]:
        with self._db_client.read() as cursor:
            cursor.execute(EntityQueries.GET_BY_ID, (str(entity_id),))
            row = cursor.fetchone()
            if row:
                return _map_entity(row)
            return None

    def get_all(self) -> list[Entity]:
        with self._db_client.read() as cursor:
            cursor.execute(EntityQueries.GET_ALL)
            return [_map_entity(row) for row in cursor.fetchall()]

    def get_by_natural_id(self, natural_id: str) -> Optional[Entity]:
        with self._db_client.read() as cursor:
            cursor.execute(EntityQueries.GET_BY_NATURAL_ID, (natural_id,))
            row = cursor.fetchone()
            if row:
                return _map_entity(row)
            return None

    def get_by_name(self, name: str) -> Optional[Entity]:
        with self._db_client.read() as cursor:
            cursor.execute(EntityQueries.GET_BY_NAME, (name,))
            row = cursor.fetchone()
            if row:
                return _map_entity(row)
            return None

    def delete_by_id(self, entity_id: UUID):
        with self._db_client.tx() as cursor:
            cursor.execute(EntityQueries.DELETE_BY_ID, (entity_id,))

    def get_disabled_entities(self) -> list[Entity]:
        with self._db_client.read() as cursor:
            cursor.execute(EntityQueries.GET_DISABLED_ENTITIES)
            return [_map_entity(row) for row in cursor.fetchall()]
