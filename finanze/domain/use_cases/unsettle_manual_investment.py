import abc

from domain.historic import UnsettleManualInvestmentRequest


class UnsettleManualInvestment(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: UnsettleManualInvestmentRequest):
        raise NotImplementedError
