import abc

from domain.historic import SettleManualInvestmentRequest


class SettleManualInvestment(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: SettleManualInvestmentRequest):
        raise NotImplementedError
