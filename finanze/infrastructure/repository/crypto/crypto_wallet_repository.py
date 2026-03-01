import json
from datetime import datetime
from typing import List
from uuid import UUID, uuid4

from dateutil.tz import tzlocal

from application.ports.crypto_wallet_port import CryptoWalletPort
from domain.crypto import CryptoWallet, HDWallet, HDAddress, AddressSource
from domain.public_key import ScriptType, CoinType
from infrastructure.repository.crypto.queries import CryptoWalletQueries
from infrastructure.repository.db.client import DBClient


class CryptoWalletRepository(CryptoWalletPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    @staticmethod
    def _map_hd_addresses(hd_addr_rows) -> list[HDAddress]:
        return [
            HDAddress(
                address=hd_row["address"],
                index=hd_row["address_index"],
                change=hd_row["change"],
                path=hd_row["derived_path"],
                pubkey=hd_row["pubkey"],
            )
            for hd_row in hd_addr_rows
        ]

    async def get_by_entity_id(
        self, entity_id: UUID, hd_addresses: bool
    ) -> List[CryptoWallet]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                CryptoWalletQueries.GET_BY_ENTITY_ID,
                (str(entity_id),),
            )
            return await self._map_crypto_rows(
                cursor, await cursor.fetchall(), hd_addresses
            )

    @staticmethod
    async def _map_crypto_rows(cursor, rows, hd_addresses: bool) -> List[CryptoWallet]:
        wallets = []
        for row in rows:
            addresses_json = row["addresses"]
            addresses = json.loads(addresses_json) if addresses_json else []
            addresses = [addr for addr in addresses if addr is not None]

            hd_wallet = None
            if row["xpub"] is not None:
                hd_wallet_addresses = []

                if hd_addresses:
                    await cursor.execute(
                        CryptoWalletQueries.GET_HD_ADDRESSES_BY_WALLET_ID,
                        (str(row["id"]),),
                    )
                    hd_addr_rows = await cursor.fetchall()
                    hd_wallet_addresses = CryptoWalletRepository._map_hd_addresses(
                        hd_addr_rows
                    )

                hd_wallet = HDWallet(
                    xpub=row["xpub"],
                    addresses=hd_wallet_addresses,
                    script_type=ScriptType(row["script_type"]),
                    coin_type=CoinType(row["coin"]),
                )

            wallet = CryptoWallet(
                id=UUID(row["id"]),
                entity_id=UUID(row["entity_id"]),
                addresses=addresses,
                name=row["name"],
                address_source=AddressSource(row["address_source"]),
                hd_wallet=hd_wallet,
            )
            wallets.append(wallet)

        return wallets

    async def exists_by_entity_and_address(self, entity_id: UUID, address: str) -> bool:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                CryptoWalletQueries.GET_BY_ENTITY_AND_ADDRESS,
                (
                    str(entity_id),
                    address,
                ),
            )
            row = await cursor.fetchone()
            if not row:
                return False

            return True

    async def exists_by_entity_and_xpub(self, entity_id: UUID, xpub: str) -> bool:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                CryptoWalletQueries.EXISTS_BY_ENTITY_AND_XPUB,
                (str(entity_id), xpub),
            )
            row = await cursor.fetchone()
            return row is not None

    async def get_connected_entities(self) -> set[UUID]:
        async with self._db_client.read() as cursor:
            await cursor.execute(CryptoWalletQueries.GET_CONNECTED_ENTITIES)
            rows = await cursor.fetchall()
            return {UUID(row["entity_id"]) for row in rows}

    async def insert(self, connection: CryptoWallet):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                CryptoWalletQueries.INSERT,
                (
                    str(connection.id),
                    str(connection.entity_id),
                    connection.name,
                    connection.address_source.value,
                    datetime.now(tzlocal()),
                ),
            )

            for address in connection.addresses:
                await cursor.execute(
                    CryptoWalletQueries.INSERT_ADDRESS,
                    (str(connection.id), address),
                )

    async def insert_hd_wallet(self, wallet_id: UUID, hd_wallet: HDWallet):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                CryptoWalletQueries.INSERT_HD_WALLET,
                (
                    str(wallet_id),
                    hd_wallet.xpub,
                    hd_wallet.script_type.value,
                    hd_wallet.coin_type.value,
                ),
            )

    async def insert_hd_addresses(self, wallet_id: UUID, addresses: list[HDAddress]):
        placeholders = ", ".join("(?, ?, ?, ?, ?, ?, ?)" for _ in addresses)
        params = []
        for address in addresses:
            params.extend(
                [
                    str(uuid4()),
                    str(wallet_id),
                    address.index,
                    address.change,
                    address.path,
                    address.address,
                    address.pubkey,
                ]
            )
        query = f"""
            INSERT INTO hd_addresses (id, hd_wallet_id, address_index, "change", derived_path, address, pubkey)
            VALUES {placeholders}
        """
        async with self._db_client.tx() as cursor:
            await cursor.execute(query, params)

    async def rename(self, wallet_connection_id: UUID, name: str):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                CryptoWalletQueries.RENAME,
                (name, str(wallet_connection_id)),
            )

    async def delete(self, wallet_connection_id: UUID):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                CryptoWalletQueries.DELETE,
                (str(wallet_connection_id),),
            )
