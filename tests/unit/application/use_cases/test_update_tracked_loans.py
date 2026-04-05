from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from application.ports.loan_calculator_port import LoanCalculatorPort
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
from domain.loan_calculator import LoanCalculationParams, LoanCalculationResult


def _build_use_case():
    position_port = AsyncMock(spec=PositionPort)
    manual_data_port = AsyncMock(spec=ManualPositionDataPort)
    calculator = AsyncMock(spec=LoanCalculatorPort)
    real_estate_port = AsyncMock()

    uc = UpdateTrackedLoansImpl(
        position_port=position_port,
        manual_position_data_port=manual_data_port,
        loan_calculator=calculator,
        real_estate_port=real_estate_port,
    )
    return uc, position_port, manual_data_port, calculator, real_estate_port


def _make_mpd(entry_id=None):
    return ManualPositionData(
        entry_id=entry_id or uuid4(),
        global_position_id=uuid4(),
        product_type=ProductType.LOAN,
        data=ManualEntryData(track=True),
    )


def _make_loan(
    id=None,
    current_installment=Dezimal(500),
    principal_outstanding=Dezimal(80000),
    interest_rate=Dezimal("0.03"),
    interest_type=InterestType.FIXED,
    installment_frequency=InstallmentFrequency.MONTHLY,
    creation=date(2020, 1, 15),
    maturity=date(2050, 1, 15),
    euribor_rate=None,
    fixed_years=None,
    fixed_interest_rate=None,
    installment_interests=None,
):
    return Loan(
        id=id or uuid4(),
        type=LoanType.MORTGAGE,
        currency="EUR",
        current_installment=current_installment,
        interest_rate=interest_rate,
        loan_amount=Dezimal(100000),
        creation=creation,
        maturity=maturity,
        principal_outstanding=principal_outstanding,
        interest_type=interest_type,
        installment_frequency=installment_frequency,
        installment_interests=installment_interests,
        fixed_interest_rate=fixed_interest_rate,
        euribor_rate=euribor_rate,
        fixed_years=fixed_years,
    )


def _make_result(
    payment=Dezimal(510),
    interests=Dezimal(200),
    outstanding=Dezimal(79500),
    inst_date=None,
):
    return LoanCalculationResult(
        current_installment_payment=payment,
        current_installment_interests=interests,
        principal_outstanding=outstanding,
        installment_date=inst_date,
    )


# ---------------------------------------------------------------------------
# TestNoEntries
# ---------------------------------------------------------------------------


class TestNoEntries:
    @pytest.mark.asyncio
    async def test_no_trackable_loans_early_return(self):
        uc, position_port, manual_data_port, calculator, _ = _build_use_case()
        manual_data_port.get_trackable_loans.return_value = []

        await uc.execute()

        calculator.calculate.assert_not_awaited()
        position_port.update_loan_position.assert_not_awaited()


# ---------------------------------------------------------------------------
# TestSingleLoan
# ---------------------------------------------------------------------------


class TestSingleLoan:
    @pytest.mark.asyncio
    async def test_updated_when_values_change(self):
        uc, position_port, manual_data_port, calculator, _ = _build_use_case()
        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan = _make_loan(id=entry_id)
        result = _make_result(payment=Dezimal(510), outstanding=Dezimal(79500))

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan
        calculator.calculate.return_value = result

        await uc.execute()

        position_port.update_loan_position.assert_awaited_once_with(
            entry_id=entry_id,
            current_installment=Dezimal(510),
            installment_interests=result.current_installment_interests,
            principal_outstanding=Dezimal(79500),
            next_payment_date=result.installment_date,
        )

    @pytest.mark.asyncio
    async def test_matured_loan_skipped(self):
        uc, position_port, manual_data_port, calculator, _ = _build_use_case()
        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan = _make_loan(id=entry_id, maturity=date.today())

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan

        await uc.execute()

        calculator.calculate.assert_not_awaited()
        position_port.update_loan_position.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_loan_not_found_skipped(self):
        uc, position_port, manual_data_port, calculator, _ = _build_use_case()
        mpd = _make_mpd()

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = None

        await uc.execute()

        calculator.calculate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_change_no_update(self):
        uc, position_port, manual_data_port, calculator, _ = _build_use_case()
        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan = _make_loan(id=entry_id, installment_interests=Dezimal(200))
        result = _make_result(
            payment=loan.current_installment,
            outstanding=loan.principal_outstanding,
        )

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan
        calculator.calculate.return_value = result

        await uc.execute()

        position_port.update_loan_position.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_new_installment_only_triggers_update(self):
        uc, position_port, manual_data_port, calculator, _ = _build_use_case()
        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan = _make_loan(id=entry_id)
        result = _make_result(
            payment=Dezimal(510),
            outstanding=loan.principal_outstanding,
        )

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan
        calculator.calculate.return_value = result

        await uc.execute()

        position_port.update_loan_position.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_new_outstanding_only_triggers_update(self):
        uc, position_port, manual_data_port, calculator, _ = _build_use_case()
        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan = _make_loan(id=entry_id)
        result = _make_result(
            payment=loan.current_installment,
            outstanding=Dezimal(79000),
        )

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan
        calculator.calculate.return_value = result

        await uc.execute()

        position_port.update_loan_position.assert_awaited_once()


# ---------------------------------------------------------------------------
# TestMultipleLoans
# ---------------------------------------------------------------------------


class TestMultipleLoans:
    @pytest.mark.asyncio
    async def test_mixed_results(self):
        uc, position_port, manual_data_port, calculator, _ = _build_use_case()
        id1, id2, id3 = uuid4(), uuid4(), uuid4()
        mpds = [
            _make_mpd(entry_id=id1),
            _make_mpd(entry_id=id2),
            _make_mpd(entry_id=id3),
        ]
        loan1 = _make_loan(id=id1)
        loan3 = _make_loan(id=id3)

        manual_data_port.get_trackable_loans.return_value = mpds

        async def get_loan(entry_id):
            if entry_id == id1:
                return loan1
            if entry_id == id2:
                return None
            return loan3

        position_port.get_loan_by_entry_id.side_effect = get_loan
        calculator.calculate.return_value = _make_result()

        await uc.execute()

        assert position_port.update_loan_position.await_count == 2

    @pytest.mark.asyncio
    async def test_exception_continues_to_next(self):
        uc, position_port, manual_data_port, calculator, _ = _build_use_case()
        id1, id2 = uuid4(), uuid4()
        mpds = [_make_mpd(entry_id=id1), _make_mpd(entry_id=id2)]
        loan2 = _make_loan(id=id2)

        manual_data_port.get_trackable_loans.return_value = mpds
        position_port.get_loan_by_entry_id.side_effect = [RuntimeError("fail"), loan2]
        calculator.calculate.return_value = _make_result()

        await uc.execute()

        assert position_port.update_loan_position.await_count == 1


# ---------------------------------------------------------------------------
# TestConcurrency
# ---------------------------------------------------------------------------


class TestConcurrency:
    @pytest.mark.asyncio
    async def test_lock_conflict_raises(self):
        uc, _, _, _, _ = _build_use_case()

        await uc._lock.acquire()
        try:
            with pytest.raises(ExecutionConflict):
                await uc.execute()
        finally:
            uc._lock.release()


# ---------------------------------------------------------------------------
# TestParamsPassed
# ---------------------------------------------------------------------------


class TestParamsPassed:
    @pytest.mark.asyncio
    async def test_fixed_loan_passes_loan_amount_and_no_ref(self):
        """FIXED loan with no tracking ref: passes loan_amount, no ref fields."""
        uc, position_port, manual_data_port, calculator, _ = _build_use_case()
        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan = _make_loan(id=entry_id)

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan
        calculator.calculate.return_value = _make_result()

        await uc.execute()

        expected_params = LoanCalculationParams(
            loan_amount=loan.loan_amount,
            interest_rate=loan.interest_rate,
            interest_type=loan.interest_type,
            euribor_rate=loan.euribor_rate,
            fixed_years=loan.fixed_years,
            start=loan.creation,
            end=loan.maturity,
            principal_outstanding=loan.principal_outstanding,
            fixed_interest_rate=loan.fixed_interest_rate,
            installment_frequency=loan.installment_frequency,
            tracking_ref_outstanding=None,
            tracking_ref_date=None,
        )
        calculator.calculate.assert_awaited_once_with(expected_params)

    @pytest.mark.asyncio
    async def test_fixed_loan_passes_tracking_ref_when_present(self):
        """FIXED loan with tracking ref: passes ref fields to calculator."""
        uc, position_port, manual_data_port, calculator, _ = _build_use_case()
        entry_id = uuid4()
        ref_outstanding = Dezimal(85000)
        ref_date = date(2025, 6, 15)
        mpd = ManualPositionData(
            entry_id=entry_id,
            global_position_id=uuid4(),
            product_type=ProductType.LOAN,
            data=ManualEntryData(
                track=True,
                tracking_ref_outstanding=ref_outstanding,
                tracking_ref_date=ref_date,
            ),
        )
        loan = _make_loan(id=entry_id)

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan
        calculator.calculate.return_value = _make_result()

        await uc.execute()

        expected_params = LoanCalculationParams(
            loan_amount=loan.loan_amount,
            interest_rate=loan.interest_rate,
            interest_type=loan.interest_type,
            euribor_rate=loan.euribor_rate,
            fixed_years=loan.fixed_years,
            start=loan.creation,
            end=loan.maturity,
            principal_outstanding=loan.principal_outstanding,
            fixed_interest_rate=loan.fixed_interest_rate,
            installment_frequency=loan.installment_frequency,
            tracking_ref_outstanding=ref_outstanding,
            tracking_ref_date=ref_date,
        )
        calculator.calculate.assert_awaited_once_with(expected_params)

    @pytest.mark.asyncio
    async def test_variable_loan_passes_no_loan_amount_and_no_ref(self):
        """VARIABLE loan: loan_amount=None, no ref fields even if present on mpd."""
        uc, position_port, manual_data_port, calculator, _ = _build_use_case()
        entry_id = uuid4()
        mpd = ManualPositionData(
            entry_id=entry_id,
            global_position_id=uuid4(),
            product_type=ProductType.LOAN,
            data=ManualEntryData(
                track=True,
                tracking_ref_outstanding=Dezimal(85000),
                tracking_ref_date=date(2025, 6, 15),
            ),
        )
        loan = _make_loan(
            id=entry_id,
            interest_type=InterestType.VARIABLE,
            euribor_rate=Dezimal("0.035"),
        )

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan
        calculator.calculate.return_value = _make_result()

        await uc.execute()

        expected_params = LoanCalculationParams(
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
            tracking_ref_outstanding=None,
            tracking_ref_date=None,
        )
        calculator.calculate.assert_awaited_once_with(expected_params)

    @pytest.mark.asyncio
    async def test_none_payment_fallback_to_loan_installment(self):
        uc, position_port, manual_data_port, calculator, _ = _build_use_case()
        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan = _make_loan(id=entry_id, current_installment=Dezimal(500))
        result = _make_result(
            payment=None,
            outstanding=Dezimal(79000),
        )

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan
        calculator.calculate.return_value = result

        await uc.execute()

        call_args = position_port.update_loan_position.call_args
        assert call_args.kwargs["current_installment"] == Dezimal(500)


# ---------------------------------------------------------------------------
# TestTrackingRefInitialization
# ---------------------------------------------------------------------------


class TestTrackingRefInitialization:
    @pytest.mark.asyncio
    async def test_fixed_loan_initializes_ref_on_first_run(self):
        """FIXED loan with no ref: lazy-initializes tracking ref."""
        uc, position_port, manual_data_port, calculator, _ = _build_use_case()
        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan = _make_loan(id=entry_id, principal_outstanding=Dezimal(80000))
        inst_date = date(2026, 5, 15)
        result = _make_result(
            payment=loan.current_installment,
            outstanding=loan.principal_outstanding,
            inst_date=inst_date,
        )

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan
        calculator.calculate.return_value = result

        await uc.execute()

        manual_data_port.update_tracking_ref.assert_awaited_once_with(
            entry_id, Dezimal(80000), inst_date
        )

    @pytest.mark.asyncio
    async def test_fixed_loan_does_not_reinitialize_ref(self):
        """FIXED loan with existing ref: does NOT call update_tracking_ref."""
        uc, position_port, manual_data_port, calculator, _ = _build_use_case()
        entry_id = uuid4()
        mpd = ManualPositionData(
            entry_id=entry_id,
            global_position_id=uuid4(),
            product_type=ProductType.LOAN,
            data=ManualEntryData(
                track=True,
                tracking_ref_outstanding=Dezimal(85000),
                tracking_ref_date=date(2025, 6, 15),
            ),
        )
        loan = _make_loan(id=entry_id)
        result = _make_result()

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan
        calculator.calculate.return_value = result

        await uc.execute()

        manual_data_port.update_tracking_ref.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_variable_loan_never_initializes_ref(self):
        """VARIABLE loan: never calls update_tracking_ref."""
        uc, position_port, manual_data_port, calculator, _ = _build_use_case()
        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan = _make_loan(
            id=entry_id,
            interest_type=InterestType.VARIABLE,
            euribor_rate=Dezimal("0.035"),
        )
        result = _make_result()

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan
        calculator.calculate.return_value = result

        await uc.execute()

        manual_data_port.update_tracking_ref.assert_not_awaited()


# ---------------------------------------------------------------------------
# TestSyncLinkedLoanFlowsAfterTrackedUpdate
# ---------------------------------------------------------------------------


class TestSyncLinkedLoanFlowsAfterTrackedUpdate:
    @pytest.mark.asyncio
    async def test_sync_called_with_updated_installment(self):
        uc, position_port, manual_data_port, calculator, real_estate_port = (
            _build_use_case()
        )
        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan = _make_loan(id=entry_id, current_installment=Dezimal(500))
        result = _make_result(payment=Dezimal(510), outstanding=Dezimal(79500))

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan
        calculator.calculate.return_value = result

        await uc.execute()

        real_estate_port.sync_linked_loan_flows.assert_awaited_once()
        synced_loan = real_estate_port.sync_linked_loan_flows.await_args[0][0]
        assert synced_loan.current_installment == Dezimal(510)

    @pytest.mark.asyncio
    async def test_sync_not_called_when_no_change(self):
        uc, position_port, manual_data_port, calculator, real_estate_port = (
            _build_use_case()
        )
        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan = _make_loan(id=entry_id, installment_interests=Dezimal(200))
        result = _make_result(
            payment=loan.current_installment,
            outstanding=loan.principal_outstanding,
        )

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan
        calculator.calculate.return_value = result

        await uc.execute()

        position_port.update_loan_position.assert_not_awaited()
        real_estate_port.sync_linked_loan_flows.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_sync_not_called_when_no_trackable_loans(self):
        uc, _, manual_data_port, _, real_estate_port = _build_use_case()
        manual_data_port.get_trackable_loans.return_value = []

        await uc.execute()

        real_estate_port.sync_linked_loan_flows.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_sync_not_called_when_loan_not_found(self):
        uc, position_port, manual_data_port, _, real_estate_port = _build_use_case()
        mpd = _make_mpd()

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = None

        await uc.execute()

        real_estate_port.sync_linked_loan_flows.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_sync_not_called_when_loan_matured(self):
        uc, position_port, manual_data_port, _, real_estate_port = _build_use_case()
        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan = _make_loan(id=entry_id, maturity=date.today())

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan

        await uc.execute()

        real_estate_port.sync_linked_loan_flows.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_sync_called_for_each_updated_loan_in_batch(self):
        uc, position_port, manual_data_port, calculator, real_estate_port = (
            _build_use_case()
        )
        id1, id2, id3 = uuid4(), uuid4(), uuid4()
        mpds = [
            _make_mpd(entry_id=id1),
            _make_mpd(entry_id=id2),
            _make_mpd(entry_id=id3),
        ]
        loan1 = _make_loan(id=id1)
        loan3 = _make_loan(id=id3)

        manual_data_port.get_trackable_loans.return_value = mpds

        async def get_loan(entry_id):
            if entry_id == id1:
                return loan1
            if entry_id == id2:
                return None
            return loan3

        position_port.get_loan_by_entry_id.side_effect = get_loan
        calculator.calculate.return_value = _make_result()

        await uc.execute()

        assert real_estate_port.sync_linked_loan_flows.await_count == 2
