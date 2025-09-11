import abc

from domain.external_entity import ExternalFetchRequest
from domain.fetch_result import FetchResult


class FetchExternalFinancialData(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, fetch_request: ExternalFetchRequest) -> FetchResult:
        raise NotImplementedError
