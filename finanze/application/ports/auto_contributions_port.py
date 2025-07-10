import abc
from uuid import UUID

from domain.auto_contributions import AutoContributions, ContributionQueryRequest
from domain.entity import Entity


class AutoContributionsPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, entity_id: UUID, data: AutoContributions):
        raise NotImplementedError

    @abc.abstractmethod
    def get_all_grouped_by_entity(
        self, query: ContributionQueryRequest
    ) -> dict[Entity, AutoContributions]:
        raise NotImplementedError
