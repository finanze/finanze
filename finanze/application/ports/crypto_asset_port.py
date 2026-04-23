import abc
from typing import Optional

from domain.crypto import CryptoAsset


class CryptoAssetRegistryPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_by_symbol(self, symbol: str) -> Optional[CryptoAsset]:
        raise NotImplementedError

    @abc.abstractmethod
    async def save(self, asset: CryptoAsset):
        raise NotImplementedError
