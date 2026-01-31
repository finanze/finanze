import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from dateutil.tz import tzlocal

from application.ports.credentials_port import CredentialsPort
from domain.native_entity import EntityCredentials, FinancialEntityCredentialsEntry
from infrastructure.repository.credentials.queries import CredentialQueries
from infrastructure.repository.db.client import DBClient


class CredentialsRepository(CredentialsPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def get(self, entity_id: UUID) -> Optional[EntityCredentials]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                CredentialQueries.GET_BY_ENTITY,
                (str(entity_id),),
            )
            row = await cursor.fetchone()
            if row:
                return EntityCredentials(**json.loads(row["credentials"]))

            return None

    async def get_available_entities(self) -> list[FinancialEntityCredentialsEntry]:
        async with self._db_client.read() as cursor:
            await cursor.execute(CredentialQueries.GET_ALL)
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
                for row in await cursor.fetchall()
            ]

    async def save(self, entity_id: UUID, credentials: EntityCredentials):
        now = datetime.now(tzlocal()).isoformat()
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                CredentialQueries.INSERT,
                (
                    str(entity_id),
                    json.dumps(credentials),
                    now,
                    now,
                ),
            )

    async def delete(self, entity_id: UUID):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                CredentialQueries.DELETE_BY_ENTITY,
                (str(entity_id),),
            )

    async def update_last_usage(self, entity_id: UUID):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                CredentialQueries.UPDATE_LAST_USED_AT,
                (datetime.now(tzlocal()).isoformat(), str(entity_id)),
            )

    async def update_expiration(self, entity_id: UUID, expiration: Optional[datetime]):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                CredentialQueries.UPDATE_EXPIRATION,
                (
                    expiration.isoformat() if expiration is not None else None,
                    str(entity_id),
                ),
            )
