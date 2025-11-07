import abc

from domain.settings import Settings
from domain.user import User


class ConfigPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def connect(self, user: User):
        raise NotImplementedError

    @abc.abstractmethod
    def disconnect(self):
        raise NotImplementedError

    @abc.abstractmethod
    def load(self) -> Settings:
        raise NotImplementedError

    @abc.abstractmethod
    def raw_load(self) -> dict:
        raise NotImplementedError

    @abc.abstractmethod
    def save(self, new_config: Settings) -> None:
        raise NotImplementedError
