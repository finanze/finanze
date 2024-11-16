import abc

from domain.bank_data import BankData


class SheetsUpdatePort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def update(self, data: dict[str, BankData]):
        raise NotImplementedError
