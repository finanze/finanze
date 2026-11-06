from typing import Optional
from uuid import UUID, uuid4

from application.ports.host_identity_port import HostIdentityPort
from infrastructure.repository.db.client import DBClient

HOST_ID_KEY = "agent_host_id"


class HostIdentityRepository(HostIdentityPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def get_host_id(self) -> UUID:
        existing = await self._read()
        if existing is not None:
            return existing

        host_id = uuid4()
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                'INSERT OR REPLACE INTO sys_config ("key", value) VALUES (?, ?)',
                (HOST_ID_KEY, str(host_id)),
            )
        return host_id

    async def _read(self) -> Optional[UUID]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                'SELECT value FROM sys_config WHERE "key" = ?', (HOST_ID_KEY,)
            )
            row = await cursor.fetchone()
        if row is None or not row["value"]:
            return None
        try:
            return UUID(row["value"])
        except ValueError:
            return None
