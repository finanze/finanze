import abc

from domain.historic import PartialAmortizeManualInvestmentRequest


class PartialAmortizeManualInvestment(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: PartialAmortizeManualInvestmentRequest):
        raise NotImplementedError
