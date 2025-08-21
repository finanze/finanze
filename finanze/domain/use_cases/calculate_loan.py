import abc

from domain.loan_calculator import LoanCalculationParams, LoanCalculationResult


class CalculateLoan(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, params: LoanCalculationParams) -> LoanCalculationResult:
        pass
