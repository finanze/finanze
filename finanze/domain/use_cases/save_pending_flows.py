import abc

from domain.earnings_expenses import PendingFlow


class SavePendingFlows(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, flows: list[PendingFlow]):
        raise NotImplementedError
