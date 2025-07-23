import abc
from uuid import UUID

from domain.global_position import CryptoInitialInvestment


class CryptoInitialInvestmentPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, entries: list[CryptoInitialInvestment]):
        raise NotImplementedError

    @abc.abstractmethod
    def delete_for_wallet_connection(self, wallet_connection_id: UUID):
        raise NotImplementedError
