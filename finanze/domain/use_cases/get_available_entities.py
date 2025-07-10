import abc

from domain.available_sources import AvailableSources


class GetAvailableEntities(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self) -> AvailableSources:
        raise NotImplementedError
