import abc
from uuid import UUID

from domain.financial_entity import FinancialEntity, Feature
from domain.scrap_result import ScrapResult


class Scrape(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self,
                      entity: UUID,
                      features: list[Feature],
                      **kwargs) -> ScrapResult:
        raise NotImplementedError
