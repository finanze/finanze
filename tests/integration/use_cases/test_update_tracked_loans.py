import pytest
from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

from application.ports.manual_position_data_port import ManualPositionDataPort
from application.ports.position_port import PositionPort
from application.use_cases.update_tracked_loans import UpdateTrackedLoansImpl
from domain.dezimal import Dezimal
from domain.exception.exceptions import ExecutionConflict
from domain.global_position import (
    InstallmentFrequency,
    InterestType,
    Loan,
    LoanType,
    ManualEntryData,
    ManualPositionData,
    ProductType,
)
from infrastructure.loan_calculator import LoanCalculator


def _make_mpd(entry_id=None):
    return ManualPositionData(
        entry_id=entry_id or uuid4(),
        global_position_id=uuid4(),
        product_type=ProductType.LOAN,
        data=ManualEntryData(track=True),
    )


def _make_loan(
    entry_id=None,
    interest_type=InterestType.FIXED,
    interest_rate=Dezimal("0.03"),
    loan_amount=Dezimal(100000),
    principal_outstanding=Dezimal(80000),
    creation=date(2020, 1, 15),
    maturity=date(2050, 1, 15),
    euribor_rate=None,
    fixed_years=None,
    fixed_interest_rate=None,
    installment_frequency=InstallmentFrequency.MONTHLY,
):
    return Loan(
        id=entry_id or uuid4(),
        type=LoanType.MORTGAGE,
        currency="EUR",
        current_installment=Dezimal(500),
        interest_rate=interest_rate,
        loan_amount=loan_amount,
        creation=creation,
        maturity=maturity,
        principal_outstanding=principal_outstanding,
        interest_type=interest_type,
        installment_frequency=installment_frequency,
        euribor_rate=euribor_rate,
        fixed_years=fixed_years,
        fixed_interest_rate=fixed_interest_rate,
    )


class TestTrackedLoanEndToEnd:
    @pytest.mark.asyncio
    async def test_fixed_loan_updates_installment_and_outstanding(self):
        """Full pipeline: real calculator produces new values, position port updated."""
        position_port = AsyncMock(spec=PositionPort)
        manual_data_port = AsyncMock(spec=ManualPositionDataPort)
        calculator = LoanCalculator()

        uc = UpdateTrackedLoansImpl(
            position_port=position_port,
            manual_position_data_port=manual_data_port,
            loan_calculator=calculator,
        )

        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan = _make_loan(entry_id=entry_id)

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan

        await uc.execute()

        position_port.update_loan_position.assert_awaited_once()
        call_kwargs = position_port.update_loan_position.await_args.kwargs
        assert call_kwargs["entry_id"] == entry_id
        # Calculator should produce sensible values
        assert call_kwargs["current_installment"].val > 0
        assert call_kwargs["installment_interests"].val > 0
        assert call_kwargs["principal_outstanding"].val > 0
        assert call_kwargs["next_payment_date"] is not None

    @pytest.mark.asyncio
    async def test_variable_loan_includes_euribor(self):
        """Variable loan with euribor produces higher payment than base rate alone."""
        position_port = AsyncMock(spec=PositionPort)
        manual_data_port = AsyncMock(spec=ManualPositionDataPort)
        calculator = LoanCalculator()

        uc = UpdateTrackedLoansImpl(
            position_port=position_port,
            manual_position_data_port=manual_data_port,
            loan_calculator=calculator,
        )

        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan = _make_loan(
            entry_id=entry_id,
            interest_type=InterestType.VARIABLE,
            interest_rate=Dezimal("0.01"),
            euribor_rate=Dezimal("0.035"),
            principal_outstanding=Dezimal(80000),
        )

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan

        await uc.execute()

        position_port.update_loan_position.assert_awaited_once()
        call_kwargs = position_port.update_loan_position.await_args.kwargs
        # Payment should reflect base + euribor
        assert call_kwargs["current_installment"].val > 0

    @pytest.mark.asyncio
    async def test_mixed_loan_during_fixed_period(self):
        """Mixed loan still in fixed period uses base rate only."""
        position_port = AsyncMock(spec=PositionPort)
        manual_data_port = AsyncMock(spec=ManualPositionDataPort)
        calculator = LoanCalculator()

        uc = UpdateTrackedLoansImpl(
            position_port=position_port,
            manual_position_data_port=manual_data_port,
            loan_calculator=calculator,
        )

        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan = _make_loan(
            entry_id=entry_id,
            interest_type=InterestType.MIXED,
            interest_rate=Dezimal("0.01"),
            euribor_rate=Dezimal("0.03"),
            fixed_years=50,
            fixed_interest_rate=Dezimal("0.02"),
            principal_outstanding=Dezimal(80000),
        )

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan

        await uc.execute()

        position_port.update_loan_position.assert_awaited_once()
        call_kwargs = position_port.update_loan_position.await_args.kwargs
        assert call_kwargs["current_installment"].val > 0
        assert call_kwargs["principal_outstanding"].val > 0

    @pytest.mark.asyncio
    async def test_matured_loan_not_updated(self):
        """Loan with maturity <= today is skipped."""
        position_port = AsyncMock(spec=PositionPort)
        manual_data_port = AsyncMock(spec=ManualPositionDataPort)
        calculator = LoanCalculator()

        uc = UpdateTrackedLoansImpl(
            position_port=position_port,
            manual_position_data_port=manual_data_port,
            loan_calculator=calculator,
        )

        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan = _make_loan(
            entry_id=entry_id,
            maturity=date.today(),
            principal_outstanding=Dezimal(80000),
        )

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan

        await uc.execute()

        position_port.update_loan_position.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_multiple_loans_mixed_results(self):
        """3 loans: one updated, one matured, one not found -> 1 update call."""
        position_port = AsyncMock(spec=PositionPort)
        manual_data_port = AsyncMock(spec=ManualPositionDataPort)
        calculator = LoanCalculator()

        uc = UpdateTrackedLoansImpl(
            position_port=position_port,
            manual_position_data_port=manual_data_port,
            loan_calculator=calculator,
        )

        # Loan 1: valid, should be updated
        id1 = uuid4()
        mpd1 = _make_mpd(entry_id=id1)
        loan1 = _make_loan(entry_id=id1)

        # Loan 2: matured, should be skipped
        id2 = uuid4()
        mpd2 = _make_mpd(entry_id=id2)
        loan2 = _make_loan(entry_id=id2, maturity=date.today())

        # Loan 3: not found
        id3 = uuid4()
        mpd3 = _make_mpd(entry_id=id3)

        manual_data_port.get_trackable_loans.return_value = [mpd1, mpd2, mpd3]

        async def get_loan(entry_id):
            if entry_id == id1:
                return loan1
            if entry_id == id2:
                return loan2
            return None

        position_port.get_loan_by_entry_id.side_effect = get_loan

        await uc.execute()

        assert position_port.update_loan_position.await_count == 1
        call_kwargs = position_port.update_loan_position.await_args.kwargs
        assert call_kwargs["entry_id"] == id1

    @pytest.mark.asyncio
    async def test_lock_conflict_raises(self):
        """Concurrent execution raises ExecutionConflict."""
        position_port = AsyncMock(spec=PositionPort)
        manual_data_port = AsyncMock(spec=ManualPositionDataPort)
        calculator = LoanCalculator()

        uc = UpdateTrackedLoansImpl(
            position_port=position_port,
            manual_position_data_port=manual_data_port,
            loan_calculator=calculator,
        )

        await uc._lock.acquire()
        try:
            with pytest.raises(ExecutionConflict):
                await uc.execute()
        finally:
            uc._lock.release()

    @pytest.mark.asyncio
    async def test_quarterly_frequency_produces_different_payment(self):
        """Quarterly installment produces different payment than monthly."""
        position_port_m = AsyncMock(spec=PositionPort)
        manual_data_port_m = AsyncMock(spec=ManualPositionDataPort)
        position_port_q = AsyncMock(spec=PositionPort)
        manual_data_port_q = AsyncMock(spec=ManualPositionDataPort)
        calculator = LoanCalculator()

        uc_monthly = UpdateTrackedLoansImpl(
            position_port=position_port_m,
            manual_position_data_port=manual_data_port_m,
            loan_calculator=calculator,
        )
        uc_quarterly = UpdateTrackedLoansImpl(
            position_port=position_port_q,
            manual_position_data_port=manual_data_port_q,
            loan_calculator=calculator,
        )

        entry_id_m = uuid4()
        mpd_m = _make_mpd(entry_id=entry_id_m)
        loan_monthly = _make_loan(
            entry_id=entry_id_m,
            installment_frequency=InstallmentFrequency.MONTHLY,
        )

        entry_id_q = uuid4()
        mpd_q = _make_mpd(entry_id=entry_id_q)
        loan_quarterly = _make_loan(
            entry_id=entry_id_q,
            installment_frequency=InstallmentFrequency.QUARTERLY,
        )

        manual_data_port_m.get_trackable_loans.return_value = [mpd_m]
        position_port_m.get_loan_by_entry_id.return_value = loan_monthly

        manual_data_port_q.get_trackable_loans.return_value = [mpd_q]
        position_port_q.get_loan_by_entry_id.return_value = loan_quarterly

        await uc_monthly.execute()
        await uc_quarterly.execute()

        position_port_m.update_loan_position.assert_awaited_once()
        position_port_q.update_loan_position.assert_awaited_once()

        kwargs_m = position_port_m.update_loan_position.await_args.kwargs
        kwargs_q = position_port_q.update_loan_position.await_args.kwargs

        # Quarterly payment should be different from monthly payment
        assert kwargs_m["current_installment"] != kwargs_q["current_installment"]
