import abc

from domain.crypto import CryptoFetchRequest
from domain.global_position import CryptoCurrencyWallet


class CryptoEntityFetcher(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def fetch(self, request: CryptoFetchRequest) -> CryptoCurrencyWallet:
        raise NotImplementedError

    def fetch_multiple(
        self, requests: list[CryptoFetchRequest]
    ) -> list[CryptoCurrencyWallet]:
        raise NotImplementedError
