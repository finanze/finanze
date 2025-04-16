import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from dateutil.tz import tzlocal

from application.ports.credentials_port import CredentialsPort
from domain.financial_entity import EntityCredentials, FinancialEntity
from infrastructure.repository.db.client import DBClient


class CredentialsRepository(CredentialsPort):

    def __init__(self, client: DBClient):
        self._db_client = client

    def get(self, entity_id: UUID) -> Optional[EntityCredentials]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT credentials FROM entity_credentials WHERE entity_id = ?",
                (str(entity_id),)
            )
            row = cursor.fetchone()
            if row:
                return EntityCredentials(**json.loads(row["credentials"]))

            return None

    def get_available_entities(self) -> list[FinancialEntity]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT e.id, e.name, e.is_real FROM financial_entities e "
                "JOIN entity_credentials ec ON e.id = ec.entity_id"
            )
            return [
                FinancialEntity(
                    id=UUID(row["id"]),
                    name=row["name"],
                    is_real=row["is_real"]
                )
                for row in cursor.fetchall()
            ]

    def save(self, entity_id: UUID, credentials: EntityCredentials):
        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                INSERT INTO entity_credentials (entity_id, credentials, last_used_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (str(entity_id),
                 json.dumps(credentials),
                 datetime.now(tzlocal()).isoformat(),
                 datetime.now(tzlocal()).isoformat())
            )

    def delete(self, entity_id: UUID):
        with self._db_client.tx() as cursor:
            cursor.execute(
                "DELETE FROM entity_credentials WHERE entity_id = ?",
                (str(entity_id),)
            )

    def update_last_usage(self, entity_id: UUID):
        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                UPDATE entity_credentials
                SET last_used_at = ?
                WHERE entity_id = ?
                """,
                (datetime.now(tzlocal()).isoformat(), str(entity_id))
            )
