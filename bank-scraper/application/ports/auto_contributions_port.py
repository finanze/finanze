import abc

from domain.auto_contributions import AutoContributions
from domain.bank import Bank


class AutoContributionsPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, source: Bank, data: AutoContributions):
        raise NotImplementedError

    @abc.abstractmethod
    def get_all_grouped_by_source(self) -> dict[str, AutoContributions]:
        raise NotImplementedError
