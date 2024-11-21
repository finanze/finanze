import abc

from domain.auto_contributions import AutoContributions
from domain.bank_data import BankGlobalPosition


class SheetsUpdatePort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def update_global_position(self, data: dict[str, BankGlobalPosition]):
        raise NotImplementedError

    @abc.abstractmethod
    def update_contributions(self, data: dict[str, AutoContributions]):
        raise NotImplementedError
