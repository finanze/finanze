from typing import Optional
from uuid import UUID

from application.ports.entity_port import EntityPort
from domain.entity import Entity
from infrastructure.repository.db.client import DBClient


def _map_entity(row) -> Entity:
    return Entity(
        id=UUID(row["id"]),
        name=row["name"],
        natural_id=row["natural_id"],
        type=row["type"],
        origin=row["origin"],
    )


class EntitySQLRepository(EntityPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def insert(self, entity: Entity):
        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                INSERT INTO entities (id, name, natural_id, type, origin)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(entity.id),
                    entity.name,
                    entity.natural_id,
                    entity.type,
                    entity.origin,
                ),
            )

    def update(self, entity: Entity):
        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                UPDATE entities
                SET name       = ?,
                    natural_id = ?,
                    type       = ?,
                    origin     = ?
                WHERE id = ?
                """,
                (
                    entity.name,
                    entity.natural_id,
                    entity.type,
                    entity.origin,
                    str(entity.id),
                ),
            )

    def get_by_id(self, entity_id: UUID) -> Optional[Entity]:
        with self._db_client.read() as cursor:
            cursor.execute("SELECT * FROM entities WHERE id = ?", (str(entity_id),))
            row = cursor.fetchone()
            if row:
                return _map_entity(row)
            return None

    def get_all(self) -> list[Entity]:
        with self._db_client.read() as cursor:
            cursor.execute("SELECT * FROM entities")
            return [_map_entity(row) for row in cursor.fetchall()]

    def get_by_natural_id(self, natural_id: str) -> Optional[Entity]:
        with self._db_client.read() as cursor:
            cursor.execute("SELECT * FROM entities WHERE natural_id = ?", (natural_id,))
            row = cursor.fetchone()
            if row:
                return _map_entity(row)
            return None

    def get_by_name(self, name: str) -> Optional[Entity]:
        with self._db_client.read() as cursor:
            cursor.execute("SELECT * FROM entities WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                return _map_entity(row)
            return None

    def delete_by_id(self, entity_id: UUID):
        with self._db_client.tx() as cursor:
            cursor.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
