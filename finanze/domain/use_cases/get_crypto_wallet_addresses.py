import abc
from uuid import UUID

from domain.crypto import CryptoWallet


class GetCryptoWalletAddresses(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, wallet_id: UUID) -> CryptoWallet:
        raise NotImplementedError
