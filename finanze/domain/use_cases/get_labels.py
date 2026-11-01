import abc

from domain.labeling import Labels


class GetLabels(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> Labels:
        raise NotImplementedError
