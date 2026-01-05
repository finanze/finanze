import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from application.ports.sessions_port import SessionsPort
from domain.entity_login import EntitySession
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.sessions.queries import SessionsQueries


class SessionsRepository(SessionsPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def get(self, entity_id: UUID) -> Optional[EntitySession]:
        with self._db_client.read() as cursor:
            cursor.execute(
                SessionsQueries.GET,
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
                SessionsQueries.INSERT,
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
                SessionsQueries.DELETE,
                (str(entity_id),),
            )
