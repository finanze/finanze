import abc

from domain.earnings_expenses import PendingFlow


class SavePendingFlow(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, flow: PendingFlow):
        raise NotImplementedError
