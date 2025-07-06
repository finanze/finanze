import abc

from domain.dezimal import Dezimal
from domain.global_position import CryptoAsset


class CryptoPriceProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def get_price(self, crypto: CryptoAsset, fiat_iso: str) -> Dezimal:
        raise NotImplementedError
