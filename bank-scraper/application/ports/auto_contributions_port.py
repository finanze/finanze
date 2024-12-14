import abc
from datetime import datetime

from domain.auto_contributions import AutoContributions


class AutoContributionsPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, entity: str, data: AutoContributions):
        raise NotImplementedError

    @abc.abstractmethod
    def get_all_grouped_by_entity(self) -> dict[str, AutoContributions]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_last_update_grouped_by_entity(self) -> dict[str, datetime]:
        raise NotImplementedError
