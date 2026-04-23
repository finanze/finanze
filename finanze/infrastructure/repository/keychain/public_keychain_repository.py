from datetime import datetime

from application.ports.public_keychain_data_port import PublicKeychainDataPort
from domain.public_keychain import PublicKeyEntry
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.keychain.queries import PublicKeychainQueries


class PublicKeychainRepository(PublicKeychainDataPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def save(self, entries: list[PublicKeyEntry]) -> None:
        async with self._db_client.tx() as cursor:
            for entry in entries:
                await cursor.execute(
                    PublicKeychainQueries.UPSERT,
                    (
                        entry.key,
                        entry.value,
                        entry.algo,
                        entry.version,
                        entry.updated_at.isoformat(),
                    ),
                )

    async def retrieve(self) -> list[PublicKeyEntry]:
        async with self._db_client.read() as cursor:
            await cursor.execute(PublicKeychainQueries.GET_ALL)
            return [
                PublicKeyEntry(
                    key=row["key"],
                    value=row["value"],
                    algo=row["algo"],
                    version=row["version"],
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
                for row in await cursor.fetchall()
            ]
