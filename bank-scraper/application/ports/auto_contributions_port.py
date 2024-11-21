import abc

from domain.auto_contributions import AutoContributions
from domain.bank import Bank


class AutoContributionsPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def upsert(self, bank: Bank, data: AutoContributions):
        raise NotImplementedError

    @abc.abstractmethod
    def get_all(self) -> dict[str, AutoContributions]:
        raise NotImplementedError
