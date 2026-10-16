import abc

from domain.cashflow import CashflowQuery, CashflowSummary


class GetCashflowSummary(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, query: CashflowQuery) -> CashflowSummary:
        raise NotImplementedError
