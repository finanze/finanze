import abc

from domain.crypto import (
    UpdateCryptoWalletConnection as UpdateCryptoWalletConnectionRequest,
)


class UpdateCryptoWalletConnection(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, data: UpdateCryptoWalletConnectionRequest):
        raise NotImplementedError
