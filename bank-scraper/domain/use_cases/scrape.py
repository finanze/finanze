import abc

from domain.financial_entity import Entity, Feature
from domain.scrap_result import ScrapResult


class Scrape(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self,
                      entity: Entity,
                      features: list[Feature],
                      **kwargs) -> ScrapResult:
        raise NotImplementedError
