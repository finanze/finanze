import abc

from domain.crypto import ConnectCryptoWallet as ConnectCryptoWalletRequest


class ConnectCryptoWallet(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, data: ConnectCryptoWalletRequest) -> None:
        raise NotImplementedError
