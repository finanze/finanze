import abc

from domain.available_sources import AvailableSources


class GetAvailableSources(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> AvailableSources:
        raise NotImplementedError
