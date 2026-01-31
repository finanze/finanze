import abc
from uuid import UUID


class DeleteCryptoWalletConnection(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, wallet_id: UUID):
        raise NotImplementedError
