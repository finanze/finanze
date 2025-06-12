import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from application.ports.sessions_port import SessionsPort
from domain.entity_login import EntitySession
from infrastructure.repository.db.client import DBClient


class SessionsRepository(SessionsPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def get(self, entity_id: UUID) -> Optional[EntitySession]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT created_at, expiration, payload FROM entity_sessions WHERE entity_id = ?",
                (str(entity_id),),
            )
            row = cursor.fetchone()
            if row:
                created_at = datetime.fromisoformat(row["created_at"])
                expiration = (
                    datetime.fromisoformat(row["expiration"])
                    if row["expiration"]
                    else None
                )
                payload = json.loads(row["payload"])
                return EntitySession(created_at, expiration, payload)
            return None

    def save(self, entity_id: UUID, session: EntitySession):
        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                INSERT INTO entity_sessions (entity_id, created_at, expiration, payload)
                VALUES (?, ?, ?, ?)
                """,
                (
                    str(entity_id),
                    session.creation.isoformat(),
                    session.expiration.isoformat() if session.expiration else None,
                    json.dumps(session.payload),
                ),
            )

    def delete(self, entity_id: UUID):
        with self._db_client.tx() as cursor:
            cursor.execute(
                "DELETE FROM entity_sessions WHERE entity_id = ?", (str(entity_id),)
            )
