from typing import Optional
from uuid import UUID

from application.ports.entity_port import EntityPort
from domain.financial_entity import FinancialEntity
from infrastructure.repository.db.client import DBClient


def _map_entity(row) -> FinancialEntity:
    return FinancialEntity(
        id=UUID(row["id"]),
        name=row["name"],
        is_real=row["is_real"]
    )


class EntitySQLRepository(EntityPort):

    def __init__(self, client: DBClient):
        self._db_client = client

    def insert(self, entity: FinancialEntity):
        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                INSERT INTO financial_entities (id, name, is_real)
                VALUES (?, ?, ?)
                """, (str(entity.id), entity.name, entity.is_real)
            )

    def get_by_id(self, entity_id: UUID) -> Optional[FinancialEntity]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM financial_entities WHERE id = ?",
                (str(entity_id),)
            )
            row = cursor.fetchone()
            if row:
                return _map_entity(row)
            return None

    def get_all(self) -> list[FinancialEntity]:
        with self._db_client.read() as cursor:
            cursor.execute("SELECT * FROM financial_entities")
            return [_map_entity(row) for row in cursor.fetchall()]

    def delete_by_id(self, entity_id: UUID):
        with self._db_client.tx() as cursor:
            cursor.execute(
                "DELETE FROM financial_entities WHERE id = ?",
                (entity_id,)
            )
