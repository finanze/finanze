import abc

from domain.crypto import CryptoFetchRequest, CryptoFetchResults


class CryptoEntityFetcher(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def fetch(self, request: CryptoFetchRequest) -> CryptoFetchResults:
        raise NotImplementedError
