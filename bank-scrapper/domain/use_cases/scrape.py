import abc

from domain.bank import Bank
from domain.scrap_result import ScrapResult


class Scrape(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, bank: Bank, params: dict) -> ScrapResult:
        raise NotImplementedError
