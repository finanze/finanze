import abc

from domain.calculations import (
    SavingsCalculationRequest,
    SavingsCalculationResult,
)


class CalculateSavings(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, request: SavingsCalculationRequest) -> SavingsCalculationResult:
        pass
