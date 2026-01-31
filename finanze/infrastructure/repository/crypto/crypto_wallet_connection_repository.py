from datetime import datetime
from typing import List, Optional
from uuid import UUID

from application.ports.crypto_wallet_connection_port import CryptoWalletConnectionPort
from dateutil.tz import tzlocal
from domain.crypto import CryptoWalletConnection
from infrastructure.repository.crypto.queries import CryptoWalletConnectionQueries
from infrastructure.repository.db.client import DBClient


class CryptoWalletConnectionRepository(CryptoWalletConnectionPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def get_by_entity_id(self, entity_id: UUID) -> List[CryptoWalletConnection]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                CryptoWalletConnectionQueries.GET_BY_ENTITY_ID,
                (str(entity_id),),
            )
            return [
                CryptoWalletConnection(
                    id=UUID(row["id"]),
                    entity_id=UUID(row["entity_id"]),
                    address=row["address"],
                    name=row["name"],
                )
                for row in await cursor.fetchall()
            ]

    async def get_by_entity_and_address(
        self, entity_id: UUID, address: str
    ) -> Optional[CryptoWalletConnection]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                CryptoWalletConnectionQueries.GET_BY_ENTITY_AND_ADDRESS,
                (
                    str(entity_id),
                    address,
                ),
            )
            row = await cursor.fetchone()
            if not row:
                return None

            return CryptoWalletConnection(
                id=UUID(row["id"]),
                entity_id=UUID(row["entity_id"]),
                address=row["address"],
                name=row["name"],
            )

    async def get_connected_entities(self) -> set[UUID]:
        async with self._db_client.read() as cursor:
            await cursor.execute(CryptoWalletConnectionQueries.GET_CONNECTED_ENTITIES)
            rows = await cursor.fetchall()
            return {UUID(row["entity_id"]) for row in rows}

    async def insert(self, connection: CryptoWalletConnection):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                CryptoWalletConnectionQueries.INSERT,
                (
                    str(connection.id),
                    str(connection.entity_id),
                    connection.address,
                    connection.name,
                    datetime.now(tzlocal()),
                ),
            )

    async def rename(self, wallet_connection_id: UUID, name: str):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                CryptoWalletConnectionQueries.RENAME,
                (name, str(wallet_connection_id)),
            )

    async def delete(self, wallet_connection_id: UUID):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                CryptoWalletConnectionQueries.DELETE,
                (str(wallet_connection_id),),
            )
