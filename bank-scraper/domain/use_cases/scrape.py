import abc

from domain.financial_entity import FinancialEntity, Feature
from domain.scrap_result import ScrapResult


class Scrape(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self,
                      entity: FinancialEntity,
                      features: list[Feature],
                      **kwargs) -> ScrapResult:
        raise NotImplementedError
