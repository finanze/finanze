import abc
from uuid import UUID

from domain.auto_contributions import AutoContributions, ContributionQueryRequest
from domain.entity import Entity
from domain.fetch_record import DataSource


class AutoContributionsPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def save(self, entity_id: UUID, data: AutoContributions, source: DataSource):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_all_grouped_by_entity(
        self, query: ContributionQueryRequest
    ) -> dict[Entity, AutoContributions]:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_by_source(self, source: DataSource):
        raise NotImplementedError
