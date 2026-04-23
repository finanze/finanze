import abc

from domain.settings import Settings


class UpdateSettings(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, new_config: Settings):
        raise NotImplementedError
