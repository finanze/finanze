from application.ports.loan_calculator_port import LoanCalculatorPort
from domain.loan_calculator import LoanCalculationParams, LoanCalculationResult
from domain.use_cases.calculate_loan import CalculateLoan


class CalculateLoanImpl(CalculateLoan):
    def __init__(self, loan_calculator: LoanCalculatorPort):
        self._loan_calculator = loan_calculator

    async def execute(self, params: LoanCalculationParams) -> LoanCalculationResult:
        return await self._loan_calculator.calculate(params)
