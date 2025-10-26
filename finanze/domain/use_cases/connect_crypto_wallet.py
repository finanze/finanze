import abc

from domain.crypto import (
    ConnectCryptoWallet as ConnectCryptoWalletRequest,
)
from domain.crypto import (
    CryptoWalletConnectionResult,
)


class ConnectCryptoWallet(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, data: ConnectCryptoWalletRequest) -> CryptoWalletConnectionResult:
        raise NotImplementedError
