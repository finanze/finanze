import abc

from domain.earnings_expenses import PendingFlowPage, PendingFlowQuery


class QueryPendingFlows(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, query: PendingFlowQuery) -> PendingFlowPage:
        raise NotImplementedError
