import abc

from domain.bank import Bank, BankFeature
from domain.scrap_result import ScrapResult


class Scrape(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self,
                      bank: Bank,
                      features: list[BankFeature],
                      **kwargs) -> ScrapResult:
        raise NotImplementedError
