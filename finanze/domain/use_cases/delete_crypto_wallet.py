import abc
from uuid import UUID


class DeleteCryptoWalletConnection(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, wallet_id: UUID):
        raise NotImplementedError
