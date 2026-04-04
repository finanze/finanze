import abc
from datetime import date

from domain.global_position import InstallmentFrequency
from domain.loan_calculator import LoanCalculationParams, LoanCalculationResult


class LoanCalculatorPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def calculate(self, params: LoanCalculationParams) -> LoanCalculationResult:
        raise NotImplementedError

    @abc.abstractmethod
    def next_installment_date(
        self, start: date, end: date, frequency: InstallmentFrequency, today: date
    ) -> date:
        raise NotImplementedError
