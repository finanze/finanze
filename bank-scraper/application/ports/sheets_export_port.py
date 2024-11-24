import abc
from datetime import datetime

from domain.auto_contributions import AutoContributions
from domain.bank_data import BankGlobalPosition
from domain.transactions import Transactions


class SheetsUpdatePort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def update_global_position(self, data: dict[str, BankGlobalPosition]):
        raise NotImplementedError

    @abc.abstractmethod
    def update_contributions(self, data: dict[str, AutoContributions], last_update: dict[str, datetime]):
        raise NotImplementedError

    @abc.abstractmethod
    def update_transactions(self, transactions: Transactions, last_update: dict[str, datetime]):
        raise NotImplementedError
