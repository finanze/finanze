import abc

from domain.dezimal import Dezimal


class CryptoPriceProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def get_price(self, crypto_symbol: str, fiat_iso: str) -> Dezimal:
        raise NotImplementedError
