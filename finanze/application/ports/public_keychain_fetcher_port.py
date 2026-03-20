import abc

from domain.public_keychain import PublicKeyEntry


class PublicKeychainFetcherPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def fetch(self) -> list[PublicKeyEntry]:
        raise NotImplementedError
