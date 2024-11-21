import abc
from datetime import datetime
from typing import Optional

from domain.bank import Bank
from domain.bank_data import BankGlobalPosition


class BankDataPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def insert(self, bank: Bank, data: BankGlobalPosition):
        raise NotImplementedError

    @abc.abstractmethod
    def get_all_data(self) -> dict[str, BankGlobalPosition]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_last_updated(self, bank: Bank) -> Optional[datetime]:
        raise NotImplementedError
