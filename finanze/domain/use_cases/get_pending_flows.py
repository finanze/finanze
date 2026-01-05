import abc

from domain.earnings_expenses import PendingFlow


class GetPendingFlows(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> list[PendingFlow]:
        raise NotImplementedError
