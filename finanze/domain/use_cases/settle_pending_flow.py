import abc

from domain.earnings_expenses import SettlePendingFlowRequest


class SettlePendingFlow(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: SettlePendingFlowRequest):
        raise NotImplementedError
