import abc

from domain.tracking import UpdateTrackedResult


class UpdateTrackedLoans(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> UpdateTrackedResult:
        raise NotImplementedError
