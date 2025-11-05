import abc
from typing import Optional

from domain.crypto import CryptoAsset


class CryptoAssetRegistryPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def get_symbols(self) -> list[str]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_symbol(self, symbol: str) -> Optional[CryptoAsset]:
        raise NotImplementedError

    @abc.abstractmethod
    def save(self, asset: CryptoAsset):
        raise NotImplementedError
