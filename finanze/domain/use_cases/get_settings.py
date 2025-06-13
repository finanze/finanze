import abc

from domain.settings import Settings


class GetSettings(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self) -> Settings:
        raise NotImplementedError
