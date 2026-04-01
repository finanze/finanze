import logging
from asyncio import Lock
from datetime import date

from application.ports.loan_calculator_port import LoanCalculatorPort
from application.ports.manual_position_data_port import ManualPositionDataPort
from application.ports.position_port import PositionPort
from domain.exception.exceptions import ExecutionConflict
from domain.loan_calculator import LoanCalculationParams
from domain.use_cases.update_tracked_loans import UpdateTrackedLoans


class UpdateTrackedLoansImpl(UpdateTrackedLoans):
    def __init__(
        self,
        position_port: PositionPort,
        manual_position_data_port: ManualPositionDataPort,
        loan_calculator: LoanCalculatorPort,
    ):
        self._position_port = position_port
        self._manual_position_data_port = manual_position_data_port
        self._loan_calculator = loan_calculator

        self._lock = Lock()
        self._log = logging.getLogger(__name__)

    async def execute(self):
        if self._lock.locked():
            raise ExecutionConflict()

        async with self._lock:
            loan_entries = await self._manual_position_data_port.get_trackable_loans()
            if not loan_entries:
                return

            self._log.info("Updating tracked loans for %d entries", len(loan_entries))

            for mpd in loan_entries:
                try:
                    await self._update_loan(mpd.entry_id)
                except Exception:
                    self._log.exception(
                        "Failed updating tracked loan for entry %s", mpd.entry_id
                    )
                    continue

    async def _update_loan(self, entry_id):
        loan = await self._position_port.get_loan_by_entry_id(entry_id)
        if not loan:
            return

        today = date.today()
        if loan.maturity <= today:
            return

        params = LoanCalculationParams(
            loan_amount=None,
            interest_rate=loan.interest_rate,
            interest_type=loan.interest_type,
            euribor_rate=loan.euribor_rate,
            fixed_years=loan.fixed_years,
            start=loan.creation,
            end=loan.maturity,
            principal_outstanding=loan.principal_outstanding,
            fixed_interest_rate=loan.fixed_interest_rate,
            installment_frequency=loan.installment_frequency,
        )

        result = await self._loan_calculator.calculate(params)

        new_installment = result.current_installment_payment or loan.current_installment
        new_interests = result.current_installment_interests
        new_outstanding = result.principal_outstanding or loan.principal_outstanding
        new_next_date = result.installment_date

        if (
            new_installment == loan.current_installment
            and new_outstanding == loan.principal_outstanding
            and (new_interests is None or new_interests == loan.installment_interests)
            and (new_next_date is None or new_next_date == loan.next_payment_date)
        ):
            return

        await self._position_port.update_loan_position(
            entry_id=entry_id,
            current_installment=new_installment,
            installment_interests=new_interests,
            principal_outstanding=new_outstanding,
            next_payment_date=new_next_date,
        )
