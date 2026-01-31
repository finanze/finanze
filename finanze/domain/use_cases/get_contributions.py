import abc

from domain.auto_contributions import EntityContributions, ContributionQueryRequest


class GetContributions(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, query: ContributionQueryRequest) -> EntityContributions:
        pass
