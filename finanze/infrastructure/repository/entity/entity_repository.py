from typing import Optional
from uuid import UUID

from application.ports.entity_port import EntityPort
from domain.entity import Entity
from infrastructure.repository.db.client import DBClient


def _map_entity(row) -> Entity:
    return Entity(
        id=UUID(row["id"]), name=row["name"], type=row["type"], is_real=row["is_real"]
    )


class EntitySQLRepository(EntityPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def insert(self, entity: Entity):
        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                INSERT INTO entities (id, name, type, is_real)
                VALUES (?, ?, ?, ?)
                """,
                (str(entity.id), entity.name, entity.type, entity.is_real),
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

    def delete_by_id(self, entity_id: UUID):
        with self._db_client.tx() as cursor:
            cursor.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
