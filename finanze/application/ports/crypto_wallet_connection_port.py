import abc
from typing import List, Optional
from uuid import UUID

from domain.crypto import CryptoWalletConnection


class CryptoWalletConnectionPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_by_entity_id(self, entity_id: UUID) -> List[CryptoWalletConnection]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_entity_and_address(
        self, entity_id: UUID, address: str
    ) -> Optional[CryptoWalletConnection]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_connected_entities(self) -> set[UUID]:
        raise NotImplementedError

    @abc.abstractmethod
    async def insert(self, connection: CryptoWalletConnection):
        raise NotImplementedError

    @abc.abstractmethod
    async def rename(self, wallet_connection_id: UUID, name: str):
        raise NotImplementedError

    @abc.abstractmethod
    async def delete(self, wallet_connection_id: UUID):
        raise NotImplementedError
