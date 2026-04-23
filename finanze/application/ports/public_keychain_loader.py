import abc

from domain.public_keychain import PublicKeychain


class PublicKeychainLoader(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def load(self) -> PublicKeychain:
        raise NotImplementedError
