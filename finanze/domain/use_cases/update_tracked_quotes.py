import abc

from domain.tracking import UpdateTrackedResult


class UpdateTrackedQuotes(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> UpdateTrackedResult:
        raise NotImplementedError
