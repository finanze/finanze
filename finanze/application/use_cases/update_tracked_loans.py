import logging
from asyncio import Lock
from datetime import date

from application.ports.loan_calculator_port import LoanCalculatorPort
from application.ports.manual_position_data_port import ManualPositionDataPort
from application.ports.position_port import PositionPort
from application.ports.real_estate_port import RealEstatePort
from domain.exception.exceptions import ExecutionConflict
from domain.global_position import InterestType, ManualPositionData
from domain.loan_calculator import LoanCalculationParams
from domain.use_cases.update_tracked_loans import UpdateTrackedLoans


class UpdateTrackedLoansImpl(UpdateTrackedLoans):
    def __init__(
        self,
        position_port: PositionPort,
        manual_position_data_port: ManualPositionDataPort,
        loan_calculator: LoanCalculatorPort,
        real_estate_port: RealEstatePort,
    ):
        self._position_port = position_port
        self._manual_position_data_port = manual_position_data_port
        self._loan_calculator = loan_calculator
        self._real_estate_port = real_estate_port

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
                    await self._update_loan(mpd)
                except Exception:
                    self._log.exception(
                        "Failed updating tracked loan for entry %s", mpd.entry_id
                    )
                    continue

    async def _update_loan(self, mpd: ManualPositionData):
        entry_id = mpd.entry_id
        loan = await self._position_port.get_loan_by_entry_id(entry_id)
        if not loan:
            return

        today = date.today()
        if loan.maturity <= today:
            return

        ref_outstanding = mpd.data.tracking_ref_outstanding if mpd.data else None
        ref_date = mpd.data.tracking_ref_date if mpd.data else None
        is_fixed = loan.interest_type == InterestType.FIXED

        params = LoanCalculationParams(
            loan_amount=loan.loan_amount if is_fixed else None,
            interest_rate=loan.interest_rate,
            interest_type=loan.interest_type,
            euribor_rate=loan.euribor_rate,
            fixed_years=loan.fixed_years,
            start=loan.creation,
            end=loan.maturity,
            principal_outstanding=loan.principal_outstanding,
            fixed_interest_rate=loan.fixed_interest_rate,
            installment_frequency=loan.installment_frequency,
            tracking_ref_outstanding=ref_outstanding if is_fixed else None,
            tracking_ref_date=ref_date if is_fixed else None,
        )
        result = await self._loan_calculator.calculate(params)

        # Lazy-initialize tracking reference for FIXED loans on first run
        if is_fixed and ref_outstanding is None:
            init_ref_outstanding = loan.principal_outstanding
            init_ref_date = result.installment_date or today
            await self._manual_position_data_port.update_tracking_ref(
                entry_id, init_ref_outstanding, init_ref_date
            )

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

        loan.current_installment = new_installment
        await self._real_estate_port.sync_linked_loan_flows(loan)
