from datetime import datetime
from uuid import uuid4

from dateutil.tz import tzlocal

from application.ports.entity_port import EntityPort
from application.ports.historic_port import HistoricPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_port import TransactionPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from application.use_cases.manual_historic_common import (
    ManualHistoricWriter,
    find_investment_entry,
    load_manual_position,
    make_investment_tx,
)
from application.use_cases.manual_position_snapshot import ManualPositionSnapshotWriter
from application.use_cases.manual_transaction_common import (
    ManualTransactionVirtualImportHelper,
)
from domain.dezimal import Dezimal
from domain.exception.exceptions import EntityNotFound, ManualInvestmentNotFound
from domain.fetch_record import DataSource
from domain.historic import PartialAmortizeManualInvestmentRequest
from domain.transactions import Transactions, TxType
from domain.use_cases.partial_amortize_manual_investment import (
    PartialAmortizeManualInvestment,
)


class PartialAmortizeManualInvestmentImpl(PartialAmortizeManualInvestment):
    def __init__(
        self,
        entity_port: EntityPort,
        position_port: PositionPort,
        transaction_port: TransactionPort,
        historic_port: HistoricPort,
        virtual_import_registry: VirtualImportRegistry,
        snapshot_writer: ManualPositionSnapshotWriter,
        transaction_handler_port: TransactionHandlerPort,
    ):
        self._entity_port = entity_port
        self._position_port = position_port
        self._transaction_port = transaction_port
        self._historic_port = historic_port
        self._virtual_import_registry = virtual_import_registry
        self._snapshot_writer = snapshot_writer
        self._transaction_handler_port = transaction_handler_port
        self._tx_helper = ManualTransactionVirtualImportHelper(virtual_import_registry)

    async def execute(self, request: PartialAmortizeManualInvestmentRequest):
        entity = await self._entity_port.get_by_id(request.entity_id)
        if entity is None:
            raise EntityNotFound(request.entity_id)

        position = await load_manual_position(
            self._virtual_import_registry, self._position_port, request.entity_id
        )
        if position is None:
            raise ManualInvestmentNotFound(request.entry_id)

        entry = find_investment_entry(position, request.product_type, request.entry_id)
        if entry is None:
            raise ManualInvestmentNotFound(request.entry_id)

        manual_key = ManualHistoricWriter.manual_key_for(entity.id, entry)
        tx_date = request.date or datetime.now(tzlocal())
        amount = request.amount or Dezimal(0)

        existing = await self._historic_port.get_by_manual_key(
            manual_key, fetch_related_txs=True
        )
        existing_id = existing.id if existing else uuid4()
        prior_txs = existing.related_txs if existing else []

        new_txs = []
        has_investment_tx = any(tx.type == TxType.INVESTMENT for tx in prior_txs)
        if request.create_investment_tx and not has_investment_tx:
            new_txs.append(
                make_investment_tx(
                    entity,
                    entry,
                    request.product_type,
                    TxType.INVESTMENT,
                    entry.amount,
                    Dezimal(0),
                    Dezimal(0),
                    entry.last_invest_date or entry.start,
                )
            )
        if amount > Dezimal(0):
            new_txs.append(
                make_investment_tx(
                    entity,
                    entry,
                    request.product_type,
                    TxType.REPAYMENT,
                    amount,
                    Dezimal(0),
                    Dezimal(0),
                    tx_date,
                )
            )
        if request.interests and request.interests > Dezimal(0):
            new_txs.append(
                make_investment_tx(
                    entity,
                    entry,
                    request.product_type,
                    TxType.INTEREST,
                    request.interests,
                    request.fees or Dezimal(0),
                    request.retentions or Dezimal(0),
                    tx_date,
                )
            )

        for tx in new_txs:
            self._tx_helper.update_derived_fields(tx)

        rewrite_snapshot = hasattr(entry, "pending_amount") and amount > Dezimal(0)
        if rewrite_snapshot:
            reduced = entry.pending_amount - amount
            entry.pending_amount = reduced if reduced > Dezimal(0) else Dezimal(0)
            position.id = uuid4()
            position.date = datetime.now(tzlocal())
            position.source = DataSource.MANUAL

        related_txs = prior_txs + new_txs

        ongoing = ManualHistoricWriter.build_entry(
            entity,
            entry,
            request.product_type,
            entry_id=existing_id,
            state=entry.state,
            effective_maturity=None,
            related_txs=related_txs,
            manual_key=manual_key,
        )

        existing_manual = await self._transaction_port.get_by_entity_and_source(
            entity.id, DataSource.MANUAL
        )
        has_transactions = bool(new_txs) or bool(
            existing_manual.account + existing_manual.investment
        )

        async with self._transaction_handler_port.start():
            if new_txs:
                await self._transaction_port.save(Transactions(investment=new_txs))
            if rewrite_snapshot:
                await self._snapshot_writer.write(
                    entity, position, compute_loan_refs=False
                )
            await self._historic_port.upsert(ongoing)
            await self._tx_helper.refresh(entity.id, has_transactions=has_transactions)
