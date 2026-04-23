import abc

from domain.public_keychain import PublicKeyEntry


class PublicKeychainDataPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def save(self, entries: list[PublicKeyEntry]) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def retrieve(self) -> list[PublicKeyEntry]:
        raise NotImplementedError
