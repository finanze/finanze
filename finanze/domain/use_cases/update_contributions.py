import abc

from domain.auto_contributions import ManualPeriodicContribution


class UpdateContributions(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, contributions: list[ManualPeriodicContribution]):
        raise NotImplementedError
