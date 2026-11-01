import abc

from domain.networth_summary import NetworthSummary, NetworthSummaryQuery


class GetNetworthSummary(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, query: NetworthSummaryQuery) -> NetworthSummary:
        raise NotImplementedError
