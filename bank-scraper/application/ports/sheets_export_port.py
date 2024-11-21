import abc

from domain.bank_data import BankGlobalPosition


class SheetsUpdatePort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def update(self, data: dict[str, BankGlobalPosition]):
        raise NotImplementedError
