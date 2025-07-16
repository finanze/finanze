import abc

from domain.crypto import CryptoFetchRequest
from domain.exception.exceptions import FeatureNotSupported
from domain.global_position import CryptoCurrencyWallet


class CryptoEntityFetcher(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def fetch(self, request: CryptoFetchRequest) -> CryptoCurrencyWallet:
        raise FeatureNotSupported
