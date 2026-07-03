import abc

from domain.earnings_expenses import PendingFlow


class UpdatePendingFlow(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, flow: PendingFlow):
        raise NotImplementedError
