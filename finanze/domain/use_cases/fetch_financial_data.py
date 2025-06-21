import abc

from domain.fetch_result import FetchResult, FetchRequest


class FetchFinancialData(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, fetch_request: FetchRequest) -> FetchResult:
        raise NotImplementedError
