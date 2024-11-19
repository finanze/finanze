import abc
from datetime import datetime
from typing import Optional

from domain.bank import Bank
from domain.bank_data import BankData


class BankDataPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def upsert_bank_data(self, bank: Bank, data: BankData):
        raise NotImplementedError

    @abc.abstractmethod
    def get_all_data(self) -> dict[str, BankData]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_last_updated(self, bank: Bank) -> Optional[datetime]:
        raise NotImplementedError
