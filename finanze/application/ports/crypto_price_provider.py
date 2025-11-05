import abc

from domain.crypto import CryptoAsset
from domain.dezimal import Dezimal


class CryptoAssetInfoProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def get_price(self, symbol: str, fiat_iso: str, **kwargs) -> Dezimal:
        raise NotImplementedError

    @abc.abstractmethod
    def get_multiple_prices(
        self, symbols: list[str], fiat_isos: list[str], **kwargs
    ) -> dict[str, dict[str, Dezimal]]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_symbol(self, symbol: str) -> list[CryptoAsset]:
        raise NotImplementedError
