import abc

from domain.fetch_result import FetchRequest, FetchResult


class FetchCryptoData(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, fetch_request: FetchRequest) -> FetchResult:
        raise NotImplementedError
