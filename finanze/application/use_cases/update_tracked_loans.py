import logging
from asyncio import Lock
from collections import defaultdict
from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from dateutil.tz import tzlocal

from application.ports.loan_calculator_port import LoanCalculatorPort
from application.ports.manual_position_data_port import ManualPositionDataPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.use_cases.manual_position_snapshot import (
    ManualPositionSnapshotWriter,
)
from domain.exception.exceptions import ExecutionConflict
from domain.global_position import (
    DataSource,
    InterestType,
    Loan,
    ManualEntryData,
    ManualPositionData,
    ProductType,
)
from domain.loan_calculator import LoanCalculationParams
from domain.tracking import UpdateTrackedResult
from domain.use_cases.update_tracked_loans import UpdateTrackedLoans


class UpdateTrackedLoansImpl(UpdateTrackedLoans):
    def __init__(
        self,
        position_port: PositionPort,
        manual_position_data_port: ManualPositionDataPort,
        loan_calculator: LoanCalculatorPort,
        snapshot_writer: ManualPositionSnapshotWriter,
        transaction_handler_port: TransactionHandlerPort,
    ):
        self._position_port = position_port
        self._manual_position_data_port = manual_position_data_port
        self._loan_calculator = loan_calculator
        self._snapshot_writer = snapshot_writer
        self._transaction_handler_port = transaction_handler_port

        self._lock = Lock()
        self._log = logging.getLogger(__name__)

    async def execute(self):
        if self._lock.locked():
            raise ExecutionConflict()

        async with self._lock:
            loan_entries = await self._manual_position_data_port.get_trackable_loans()
            if not loan_entries:
                return UpdateTrackedResult(had_tracked=False)

            grouped: dict[UUID, list[ManualPositionData]] = defaultdict(list)
            for mpd in loan_entries:
                grouped[mpd.global_position_id].append(mpd)

            self._log.info(
                "Updating tracked loans for %d entries across %d positions",
                len(loan_entries),
                len(grouped),
            )

            changed_entities: set[UUID] = set()
            changed_entries = 0
            for global_position_id, entries in grouped.items():
                try:
                    result = await self._refresh_position(global_position_id, entries)
                    if result is not None:
                        entity_id, entry_count = result
                        changed_entities.add(entity_id)
                        changed_entries += entry_count
                except Exception:
                    self._log.exception(
                        "Failed updating tracked loans for position %s",
                        global_position_id,
                    )
                    continue

            self._log.info(
                "Finished updating tracked loans: %d changed entities, "
                "%d changed entries",
                len(changed_entities),
                changed_entries,
            )

            return UpdateTrackedResult(
                had_tracked=True, changed_entities=list(changed_entities)
            )

    async def _refresh_position(
        self,
        global_position_id: UUID,
        entries: list[ManualPositionData],
    ) -> Optional[tuple[UUID, int]]:
        position = await self._position_port.get_by_id(global_position_id)
        if not position:
            return None

        container = position.products.get(ProductType.LOAN)
        if not (container and getattr(container, "entries", None)):
            return None

        data_by_entry: dict[UUID, ManualEntryData] = {
            mpd.entry_id: mpd.data for mpd in entries if mpd.data
        }

        changed_entries = 0
        for loan in container.entries:
            data = data_by_entry.get(loan.id)
            if data is None:
                continue
            self._apply_tracking_ref(loan, data)
            if await self._recalculate_loan(loan, data):
                changed_entries += 1

        if not changed_entries:
            return None

        position.id = uuid4()
        position.date = datetime.now(tzlocal())
        position.source = DataSource.MANUAL

        async with self._transaction_handler_port.start():
            await self._snapshot_writer.write(
                position.entity, position, compute_loan_refs=False
            )

        return position.entity.id, changed_entries

    def _apply_tracking_ref(self, loan: Loan, data: ManualEntryData) -> None:
        if loan.manual_data is None:
            return

        if loan.interest_type != InterestType.FIXED:
            loan.manual_data.tracking_ref_outstanding = None
            loan.manual_data.tracking_ref_date = None
            return

        if (
            data.tracking_ref_outstanding is not None
            and data.tracking_ref_date is not None
        ):
            loan.manual_data.tracking_ref_outstanding = data.tracking_ref_outstanding
            loan.manual_data.tracking_ref_date = data.tracking_ref_date
            return

        if loan.maturity > date.today():
            loan.manual_data.tracking_ref_outstanding = loan.principal_outstanding
            loan.manual_data.tracking_ref_date = (
                self._loan_calculator.next_installment_date(
                    loan.creation,
                    loan.maturity,
                    loan.installment_frequency,
                    date.today(),
                )
            )

    async def _recalculate_loan(self, loan: Loan, data: ManualEntryData) -> bool:
        today = date.today()
        if loan.maturity <= today:
            return False

        is_fixed = loan.interest_type == InterestType.FIXED
        ref_outstanding = data.tracking_ref_outstanding
        ref_date = data.tracking_ref_date

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
            return False

        loan.current_installment = new_installment
        loan.installment_interests = new_interests
        loan.principal_outstanding = new_outstanding
        if new_next_date is not None:
            loan.next_payment_date = new_next_date

        return True
