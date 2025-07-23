from datetime import datetime
from typing import List, Optional
from uuid import UUID

from application.ports.crypto_wallet_connection_port import CryptoWalletConnectionPort
from dateutil.tz import tzlocal
from domain.crypto import CryptoWalletConnection
from infrastructure.repository.db.client import DBClient


class CryptoWalletConnectionRepository(CryptoWalletConnectionPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def get_by_entity_id(self, entity_id: UUID) -> List[CryptoWalletConnection]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM crypto_wallet_connections WHERE entity_id = ?",
                (str(entity_id),),
            )
            return [
                CryptoWalletConnection(
                    id=UUID(row["id"]),
                    entity_id=UUID(row["entity_id"]),
                    address=row["address"],
                    name=row["name"],
                )
                for row in cursor.fetchall()
            ]

    def get_by_entity_and_address(
        self, entity_id: UUID, address: str
    ) -> Optional[CryptoWalletConnection]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM crypto_wallet_connections WHERE entity_id = ? AND address = ?",
                (
                    str(entity_id),
                    address,
                ),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return CryptoWalletConnection(
                id=UUID(row["id"]),
                entity_id=UUID(row["entity_id"]),
                address=row["address"],
                name=row["name"],
            )

    def get_connected_entities(self) -> set[UUID]:
        with self._db_client.read() as cursor:
            cursor.execute("SELECT DISTINCT(entity_id) FROM crypto_wallet_connections")
            rows = cursor.fetchall()
            return {UUID(row["entity_id"]) for row in rows}

    def insert(self, connection: CryptoWalletConnection):
        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                INSERT INTO crypto_wallet_connections (id, entity_id, address, name, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(connection.id),
                    str(connection.entity_id),
                    connection.address,
                    connection.name,
                    datetime.now(tzlocal()),
                ),
            )

    def rename(self, wallet_connection_id: UUID, name: str):
        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                UPDATE crypto_wallet_connections
                SET name = ?
                WHERE id = ?
                """,
                (name, str(wallet_connection_id)),
            )

    def delete(self, wallet_connection_id: UUID):
        with self._db_client.tx() as cursor:
            cursor.execute(
                "DELETE FROM crypto_wallet_connections WHERE id = ?",
                (str(wallet_connection_id),),
            )
