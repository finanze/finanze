import abc

from domain.calculations import (
    SavingsCalculationRequest,
    SavingsCalculationResult,
)


class CalculateSavings(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(
        self, request: SavingsCalculationRequest
    ) -> SavingsCalculationResult:
        pass
