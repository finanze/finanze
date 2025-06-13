import abc

from domain.scrap_result import ScrapResult, ScrapRequest


class Scrape(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, scrap_request: ScrapRequest) -> ScrapResult:
        raise NotImplementedError
