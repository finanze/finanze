import abc

from domain.settings import PartialSettings


class UpdateSettings(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, new_config: PartialSettings):
        raise NotImplementedError
