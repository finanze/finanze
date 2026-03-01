import abc
from typing import List
from uuid import UUID

from domain.crypto import CryptoWallet, HDWallet, HDAddress


class CryptoWalletPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def insert_hd_wallet(self, wallet_id: UUID, hd_wallet: HDWallet):
        raise NotImplementedError

    @abc.abstractmethod
    async def insert_hd_addresses(self, wallet_id: UUID, addresses: list[HDAddress]):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_entity_id(
        self, entity_id: UUID, hd_addresses: bool
    ) -> List[CryptoWallet]:
        raise NotImplementedError

    @abc.abstractmethod
    async def exists_by_entity_and_address(self, entity_id: UUID, address: str) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    async def exists_by_entity_and_xpub(self, entity_id: UUID, xpub: str) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_connected_entities(self) -> set[UUID]:
        raise NotImplementedError

    @abc.abstractmethod
    async def insert(self, connection: CryptoWallet):
        raise NotImplementedError

    @abc.abstractmethod
    async def rename(self, wallet_connection_id: UUID, name: str):
        raise NotImplementedError

    @abc.abstractmethod
    async def delete(self, wallet_connection_id: UUID):
        raise NotImplementedError
