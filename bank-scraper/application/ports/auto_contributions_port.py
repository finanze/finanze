import abc
from datetime import datetime

from domain.auto_contributions import AutoContributions
from domain.financial_entity import FinancialEntity


class AutoContributionsPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, entity_id: int, data: AutoContributions):
        raise NotImplementedError

    @abc.abstractmethod
    def get_all_grouped_by_entity(self) -> dict[FinancialEntity, AutoContributions]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_last_update_grouped_by_entity(self) -> dict[FinancialEntity, datetime]:
        raise NotImplementedError
