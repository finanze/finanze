import abc

from domain.settings import Settings


class UpdateSettings(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def execute(self, new_config: Settings):
        raise NotImplementedError
