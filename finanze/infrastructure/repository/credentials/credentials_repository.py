import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from application.ports.credentials_port import CredentialsPort
from dateutil.tz import tzlocal
from domain.native_entity import EntityCredentials, FinancialEntityCredentialsEntry
from infrastructure.repository.db.client import DBClient


class CredentialsRepository(CredentialsPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def get(self, entity_id: UUID) -> Optional[EntityCredentials]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT credentials FROM entity_credentials WHERE entity_id = ?",
                (str(entity_id),),
            )
            row = cursor.fetchone()
            if row:
                return EntityCredentials(**json.loads(row["credentials"]))

            return None

    def get_available_entities(self) -> list[FinancialEntityCredentialsEntry]:
        with self._db_client.read() as cursor:
            cursor.execute("SELECT * FROM entity_credentials")
            return [
                FinancialEntityCredentialsEntry(
                    entity_id=UUID(row["entity_id"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    last_used_at=datetime.fromisoformat(row["last_used_at"])
                    if row["last_used_at"]
                    else None,
                    expiration=datetime.fromisoformat(row["expiration"])
                    if row["expiration"]
                    else None,
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
                (
                    str(entity_id),
                    json.dumps(credentials),
                    datetime.now(tzlocal()).isoformat(),
                    datetime.now(tzlocal()).isoformat(),
                ),
            )

    def delete(self, entity_id: UUID):
        with self._db_client.tx() as cursor:
            cursor.execute(
                "DELETE FROM entity_credentials WHERE entity_id = ?", (str(entity_id),)
            )

    def update_last_usage(self, entity_id: UUID):
        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                UPDATE entity_credentials
                SET last_used_at = ?
                WHERE entity_id = ?
                """,
                (datetime.now(tzlocal()).isoformat(), str(entity_id)),
            )

    def update_expiration(self, entity_id: UUID, expiration: Optional[datetime]):
        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                UPDATE entity_credentials
                SET expiration = ?
                WHERE entity_id = ?
                """,
                (
                    expiration.isoformat() if expiration is not None else None,
                    str(entity_id),
                ),
            )
