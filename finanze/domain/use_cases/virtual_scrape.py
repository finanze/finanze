import abc

from domain.scrap_result import ScrapResult


class VirtualScrape(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> ScrapResult:
        raise NotImplementedError
