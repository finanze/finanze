import abc

from domain.local_model import LocalModelsOverview


class GetLocalModels(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, refresh: bool = False) -> LocalModelsOverview:
        raise NotImplementedError
