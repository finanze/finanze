from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from application.ports.loan_calculator_port import LoanCalculatorPort
from application.ports.manual_position_data_port import ManualPositionDataPort
from application.ports.position_port import PositionPort
from application.use_cases.manual_position_snapshot import (
    ManualPositionSnapshotWriter,
)
from application.use_cases.update_tracked_loans import UpdateTrackedLoansImpl
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.exception.exceptions import ExecutionConflict
from domain.global_position import (
    DataSource,
    GlobalPosition,
    InstallmentFrequency,
    InterestType,
    Loan,
    Loans,
    LoanType,
    ManualEntryData,
    ManualPositionData,
    ProductType,
)
from domain.loan_calculator import LoanCalculationParams, LoanCalculationResult


class _NoopTransaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *args):
        return False


def _make_transaction_handler():
    handler = MagicMock()
    handler.start = MagicMock(return_value=_NoopTransaction())
    return handler


def _make_entity() -> Entity:
    return Entity(
        id=uuid4(),
        name="Manual",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )


def _build_use_case():
    position_port = AsyncMock(spec=PositionPort)
    position_port.get_by_id.return_value = None
    manual_data_port = AsyncMock(spec=ManualPositionDataPort)
    calculator = AsyncMock(spec=LoanCalculatorPort)
    snapshot_writer = AsyncMock(spec=ManualPositionSnapshotWriter)
    transaction_handler = _make_transaction_handler()

    uc = UpdateTrackedLoansImpl(
        position_port=position_port,
        manual_position_data_port=manual_data_port,
        loan_calculator=calculator,
        snapshot_writer=snapshot_writer,
        transaction_handler_port=transaction_handler,
    )
    return uc, position_port, manual_data_port, calculator, snapshot_writer


def _make_mpd(entry_id=None, global_position_id=None, data=None):
    return ManualPositionData(
        entry_id=entry_id or uuid4(),
        global_position_id=global_position_id or uuid4(),
        product_type=ProductType.LOAN,
        data=data or ManualEntryData(track=True),
    )


def _make_position(global_position_id=None, loans=None, entity=None) -> GlobalPosition:
    return GlobalPosition(
        id=global_position_id or uuid4(),
        entity=entity or _make_entity(),
        products={ProductType.LOAN: Loans(entries=loans or [])},
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
        uc, position_port, manual_data_port, calculator, snapshot_writer = (
            _build_use_case()
        )
        manual_data_port.get_trackable_loans.return_value = []

        await uc.execute()

        calculator.calculate.assert_not_awaited()
        snapshot_writer.write.assert_not_awaited()


# ---------------------------------------------------------------------------
# TestSingleLoan
# ---------------------------------------------------------------------------


class TestSingleLoan:
    @pytest.mark.asyncio
    async def test_updated_when_values_change(self):
        uc, position_port, manual_data_port, calculator, snapshot_writer = (
            _build_use_case()
        )
        entry_id = uuid4()
        gpid = uuid4()
        loan = _make_loan(id=entry_id)
        position = _make_position(global_position_id=gpid, loans=[loan])
        mpd = _make_mpd(entry_id=entry_id, global_position_id=gpid)
        result = _make_result(payment=Dezimal(510), outstanding=Dezimal(79500))

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
        calculator.calculate.return_value = result

        await uc.execute()

        snapshot_writer.write.assert_awaited_once()
        written_entity, written_position = snapshot_writer.write.await_args[0]
        assert written_entity is position.entity
        assert written_position is position
        assert written_position.source == DataSource.MANUAL
        assert loan.current_installment == Dezimal(510)
        assert loan.principal_outstanding == Dezimal(79500)
        assert loan.installment_interests == result.current_installment_interests
        assert loan.next_payment_date == result.installment_date

    @pytest.mark.asyncio
    async def test_matured_loan_skipped(self):
        uc, position_port, manual_data_port, calculator, snapshot_writer = (
            _build_use_case()
        )
        entry_id = uuid4()
        gpid = uuid4()
        loan = _make_loan(id=entry_id, maturity=date.today())
        position = _make_position(global_position_id=gpid, loans=[loan])
        mpd = _make_mpd(entry_id=entry_id, global_position_id=gpid)

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position

        await uc.execute()

        calculator.calculate.assert_not_awaited()
        snapshot_writer.write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_position_not_found_skipped(self):
        uc, position_port, manual_data_port, calculator, snapshot_writer = (
            _build_use_case()
        )
        mpd = _make_mpd()

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = None

        await uc.execute()

        calculator.calculate.assert_not_awaited()
        snapshot_writer.write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_loan_entry_not_in_position_skipped(self):
        uc, position_port, manual_data_port, calculator, snapshot_writer = (
            _build_use_case()
        )
        gpid = uuid4()
        position = _make_position(
            global_position_id=gpid, loans=[_make_loan(id=uuid4())]
        )
        mpd = _make_mpd(entry_id=uuid4(), global_position_id=gpid)

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
        calculator.calculate.return_value = _make_result()

        await uc.execute()

        calculator.calculate.assert_not_awaited()
        snapshot_writer.write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_change_no_snapshot(self):
        uc, position_port, manual_data_port, calculator, snapshot_writer = (
            _build_use_case()
        )
        entry_id = uuid4()
        gpid = uuid4()
        loan = _make_loan(id=entry_id, installment_interests=Dezimal(200))
        position = _make_position(global_position_id=gpid, loans=[loan])
        mpd = _make_mpd(entry_id=entry_id, global_position_id=gpid)
        result = _make_result(
            payment=loan.current_installment,
            outstanding=loan.principal_outstanding,
        )

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
        calculator.calculate.return_value = result

        await uc.execute()

        snapshot_writer.write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_new_installment_only_triggers_snapshot(self):
        uc, position_port, manual_data_port, calculator, snapshot_writer = (
            _build_use_case()
        )
        entry_id = uuid4()
        gpid = uuid4()
        loan = _make_loan(id=entry_id)
        position = _make_position(global_position_id=gpid, loans=[loan])
        mpd = _make_mpd(entry_id=entry_id, global_position_id=gpid)
        result = _make_result(
            payment=Dezimal(510),
            outstanding=loan.principal_outstanding,
        )

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
        calculator.calculate.return_value = result

        await uc.execute()

        snapshot_writer.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_new_outstanding_only_triggers_snapshot(self):
        uc, position_port, manual_data_port, calculator, snapshot_writer = (
            _build_use_case()
        )
        entry_id = uuid4()
        gpid = uuid4()
        loan = _make_loan(id=entry_id)
        position = _make_position(global_position_id=gpid, loans=[loan])
        mpd = _make_mpd(entry_id=entry_id, global_position_id=gpid)
        result = _make_result(
            payment=loan.current_installment,
            outstanding=Dezimal(79000),
        )

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
        calculator.calculate.return_value = result

        await uc.execute()

        snapshot_writer.write.assert_awaited_once()


# ---------------------------------------------------------------------------
# TestMultipleLoans
# ---------------------------------------------------------------------------


class TestMultipleLoans:
    @pytest.mark.asyncio
    async def test_mixed_results(self):
        uc, position_port, manual_data_port, calculator, snapshot_writer = (
            _build_use_case()
        )
        id1, id2, id3 = uuid4(), uuid4(), uuid4()
        g1, g2, g3 = uuid4(), uuid4(), uuid4()
        mpds = [
            _make_mpd(entry_id=id1, global_position_id=g1),
            _make_mpd(entry_id=id2, global_position_id=g2),
            _make_mpd(entry_id=id3, global_position_id=g3),
        ]
        pos1 = _make_position(global_position_id=g1, loans=[_make_loan(id=id1)])
        pos3 = _make_position(global_position_id=g3, loans=[_make_loan(id=id3)])

        manual_data_port.get_trackable_loans.return_value = mpds

        async def get_by_id(global_position_id):
            if global_position_id == g1:
                return pos1
            if global_position_id == g2:
                return None
            return pos3

        position_port.get_by_id.side_effect = get_by_id
        calculator.calculate.return_value = _make_result()

        await uc.execute()

        assert snapshot_writer.write.await_count == 2

    @pytest.mark.asyncio
    async def test_exception_continues_to_next(self):
        uc, position_port, manual_data_port, calculator, snapshot_writer = (
            _build_use_case()
        )
        id1, id2 = uuid4(), uuid4()
        g1, g2 = uuid4(), uuid4()
        mpds = [
            _make_mpd(entry_id=id1, global_position_id=g1),
            _make_mpd(entry_id=id2, global_position_id=g2),
        ]
        pos2 = _make_position(global_position_id=g2, loans=[_make_loan(id=id2)])

        manual_data_port.get_trackable_loans.return_value = mpds

        async def get_by_id(global_position_id):
            if global_position_id == g1:
                raise RuntimeError("fail")
            return pos2

        position_port.get_by_id.side_effect = get_by_id
        calculator.calculate.return_value = _make_result()

        await uc.execute()

        assert snapshot_writer.write.await_count == 1

    @pytest.mark.asyncio
    async def test_multiple_loans_same_position_one_snapshot(self):
        uc, position_port, manual_data_port, calculator, snapshot_writer = (
            _build_use_case()
        )
        id1, id2 = uuid4(), uuid4()
        gpid = uuid4()
        loan1 = _make_loan(id=id1)
        loan2 = _make_loan(id=id2)
        position = _make_position(global_position_id=gpid, loans=[loan1, loan2])
        mpds = [
            _make_mpd(entry_id=id1, global_position_id=gpid),
            _make_mpd(entry_id=id2, global_position_id=gpid),
        ]

        manual_data_port.get_trackable_loans.return_value = mpds
        position_port.get_by_id.return_value = position
        calculator.calculate.return_value = _make_result(
            payment=Dezimal(510), outstanding=Dezimal(79500)
        )

        await uc.execute()

        snapshot_writer.write.assert_awaited_once()


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
        gpid = uuid4()
        loan = _make_loan(id=entry_id)
        position = _make_position(global_position_id=gpid, loans=[loan])
        mpd = _make_mpd(entry_id=entry_id, global_position_id=gpid)

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
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
            principal_outstanding=Dezimal(80000),
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
        gpid = uuid4()
        ref_outstanding = Dezimal(85000)
        ref_date = date(2025, 6, 15)
        mpd = _make_mpd(
            entry_id=entry_id,
            global_position_id=gpid,
            data=ManualEntryData(
                track=True,
                tracking_ref_outstanding=ref_outstanding,
                tracking_ref_date=ref_date,
            ),
        )
        loan = _make_loan(id=entry_id)
        position = _make_position(global_position_id=gpid, loans=[loan])

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
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
            principal_outstanding=Dezimal(80000),
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
        gpid = uuid4()
        mpd = _make_mpd(
            entry_id=entry_id,
            global_position_id=gpid,
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
        position = _make_position(global_position_id=gpid, loans=[loan])

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
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
            principal_outstanding=Dezimal(80000),
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
        gpid = uuid4()
        loan = _make_loan(id=entry_id, current_installment=Dezimal(500))
        position = _make_position(global_position_id=gpid, loans=[loan])
        mpd = _make_mpd(entry_id=entry_id, global_position_id=gpid)
        result = _make_result(
            payment=None,
            outstanding=Dezimal(79000),
        )

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
        calculator.calculate.return_value = result

        await uc.execute()

        assert loan.current_installment == Dezimal(500)
        assert loan.principal_outstanding == Dezimal(79000)


# ---------------------------------------------------------------------------
# TestResult
# ---------------------------------------------------------------------------


class TestResult:
    @pytest.mark.asyncio
    async def test_no_trackable_loans_returns_not_tracked(self):
        uc, _, manual_data_port, _, _ = _build_use_case()
        manual_data_port.get_trackable_loans.return_value = []

        result = await uc.execute()

        assert result.had_tracked is False
        assert result.changed is False
        assert result.changed_entities == []

    @pytest.mark.asyncio
    async def test_changed_loan_returns_entity_id(self):
        uc, position_port, manual_data_port, calculator, _ = _build_use_case()
        entry_id = uuid4()
        gpid = uuid4()
        entity = _make_entity()
        loan = _make_loan(id=entry_id)
        position = _make_position(global_position_id=gpid, loans=[loan], entity=entity)
        mpd = _make_mpd(entry_id=entry_id, global_position_id=gpid)

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
        calculator.calculate.return_value = _make_result(
            payment=Dezimal(510), outstanding=Dezimal(79500)
        )

        result = await uc.execute()

        assert result.had_tracked is True
        assert result.changed is True
        assert result.changed_entities == [entity.id]

    @pytest.mark.asyncio
    async def test_unchanged_loan_returns_no_changed_entities(self):
        uc, position_port, manual_data_port, calculator, _ = _build_use_case()
        entry_id = uuid4()
        gpid = uuid4()
        loan = _make_loan(id=entry_id, installment_interests=Dezimal(200))
        position = _make_position(global_position_id=gpid, loans=[loan])
        mpd = _make_mpd(entry_id=entry_id, global_position_id=gpid)
        result = _make_result(
            payment=loan.current_installment,
            outstanding=loan.principal_outstanding,
        )

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
        calculator.calculate.return_value = result

        outcome = await uc.execute()

        assert outcome.had_tracked is True
        assert outcome.changed is False
        assert outcome.changed_entities == []


# ---------------------------------------------------------------------------
# TestTrackingRefPreservation
# ---------------------------------------------------------------------------


class TestTrackingRefPreservation:
    @pytest.mark.asyncio
    async def test_writer_called_with_compute_loan_refs_false(self):
        uc, position_port, manual_data_port, calculator, snapshot_writer = (
            _build_use_case()
        )
        entry_id = uuid4()
        gpid = uuid4()
        loan = _make_loan(id=entry_id)
        loan.manual_data = ManualEntryData(track=True)
        position = _make_position(global_position_id=gpid, loans=[loan])
        mpd = _make_mpd(entry_id=entry_id, global_position_id=gpid)

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
        calculator.calculate.return_value = _make_result(
            payment=Dezimal(510), outstanding=Dezimal(79500)
        )

        await uc.execute()

        snapshot_writer.write.assert_awaited_once()
        assert snapshot_writer.write.await_args.kwargs["compute_loan_refs"] is False

    @pytest.mark.asyncio
    async def test_fixed_existing_ref_preserved_not_reanchored(self):
        uc, position_port, manual_data_port, calculator, snapshot_writer = (
            _build_use_case()
        )
        entry_id = uuid4()
        gpid = uuid4()
        ref_outstanding = Dezimal(85000)
        ref_date = date(2025, 6, 15)
        loan = _make_loan(id=entry_id)
        loan.manual_data = ManualEntryData(
            track=True,
            tracking_ref_outstanding=ref_outstanding,
            tracking_ref_date=ref_date,
        )
        position = _make_position(global_position_id=gpid, loans=[loan])
        mpd = _make_mpd(
            entry_id=entry_id,
            global_position_id=gpid,
            data=ManualEntryData(
                track=True,
                tracking_ref_outstanding=ref_outstanding,
                tracking_ref_date=ref_date,
            ),
        )

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
        calculator.calculate.return_value = _make_result(
            payment=Dezimal(510), outstanding=Dezimal(79500)
        )

        await uc.execute()

        assert loan.manual_data.tracking_ref_outstanding == ref_outstanding
        assert loan.manual_data.tracking_ref_date == ref_date
        calculator.next_installment_date.assert_not_called()

    @pytest.mark.asyncio
    async def test_fixed_missing_ref_lazy_initialized(self):
        uc, position_port, manual_data_port, calculator, snapshot_writer = (
            _build_use_case()
        )
        entry_id = uuid4()
        gpid = uuid4()
        lazy_date = date(2026, 7, 15)
        loan = _make_loan(id=entry_id, principal_outstanding=Dezimal(80000))
        loan.manual_data = ManualEntryData(track=True)
        position = _make_position(global_position_id=gpid, loans=[loan])
        mpd = _make_mpd(entry_id=entry_id, global_position_id=gpid)

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
        calculator.next_installment_date.return_value = lazy_date
        calculator.calculate.return_value = _make_result(
            payment=Dezimal(510), outstanding=Dezimal(79500)
        )

        await uc.execute()

        assert loan.manual_data.tracking_ref_outstanding == Dezimal(80000)
        assert loan.manual_data.tracking_ref_date == lazy_date

    @pytest.mark.asyncio
    async def test_variable_ref_cleared_even_if_present(self):
        uc, position_port, manual_data_port, calculator, snapshot_writer = (
            _build_use_case()
        )
        entry_id = uuid4()
        gpid = uuid4()
        loan = _make_loan(
            id=entry_id,
            interest_type=InterestType.VARIABLE,
            euribor_rate=Dezimal("0.035"),
        )
        loan.manual_data = ManualEntryData(
            track=True,
            tracking_ref_outstanding=Dezimal(85000),
            tracking_ref_date=date(2025, 6, 15),
        )
        position = _make_position(global_position_id=gpid, loans=[loan])
        mpd = _make_mpd(
            entry_id=entry_id,
            global_position_id=gpid,
            data=ManualEntryData(
                track=True,
                tracking_ref_outstanding=Dezimal(85000),
                tracking_ref_date=date(2025, 6, 15),
            ),
        )

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
        calculator.calculate.return_value = _make_result(
            payment=Dezimal(510), outstanding=Dezimal(79500)
        )

        await uc.execute()

        assert loan.manual_data.tracking_ref_outstanding is None
        assert loan.manual_data.tracking_ref_date is None
        calculator.next_installment_date.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_tracked_loan_preserved_in_mixed_position(self):
        uc, position_port, manual_data_port, calculator, snapshot_writer = (
            _build_use_case()
        )
        tracked_id = uuid4()
        untracked_id = uuid4()
        gpid = uuid4()
        tracked = _make_loan(id=tracked_id)
        tracked.manual_data = ManualEntryData(track=True)
        untracked = _make_loan(
            id=untracked_id,
            current_installment=Dezimal(400),
            principal_outstanding=Dezimal(60000),
            installment_interests=Dezimal(150),
        )
        untracked.manual_data = ManualEntryData(
            track=False,
            tracking_ref_outstanding=Dezimal(61000),
            tracking_ref_date=date(2024, 1, 10),
        )
        position = _make_position(global_position_id=gpid, loans=[tracked, untracked])
        mpd = _make_mpd(entry_id=tracked_id, global_position_id=gpid)

        manual_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
        calculator.calculate.return_value = _make_result(
            payment=Dezimal(510), outstanding=Dezimal(79500)
        )

        await uc.execute()

        snapshot_writer.write.assert_awaited_once()
        assert untracked.current_installment == Dezimal(400)
        assert untracked.principal_outstanding == Dezimal(60000)
        assert untracked.installment_interests == Dezimal(150)
        assert untracked.manual_data.tracking_ref_outstanding == Dezimal(61000)
        assert untracked.manual_data.tracking_ref_date == date(2024, 1, 10)
