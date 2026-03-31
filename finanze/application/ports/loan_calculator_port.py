import abc

from domain.loan_calculator import LoanCalculationParams, LoanCalculationResult


class LoanCalculatorPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def calculate(self, params: LoanCalculationParams) -> LoanCalculationResult:
        raise NotImplementedError
