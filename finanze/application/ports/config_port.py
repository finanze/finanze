import abc

from domain.settings import Settings


class ConfigPort(metaclass=abc.ABCMeta):

    def load(self) -> Settings:
        raise NotImplementedError

    def save(self, new_config: Settings) -> None:
        raise NotImplementedError
