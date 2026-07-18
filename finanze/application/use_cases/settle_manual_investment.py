from datetime import datetime

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
    settlement_tx_ref,
)
from application.use_cases.manual_position_snapshot import ManualPositionSnapshotWriter
from application.use_cases.manual_transaction_common import (
    ManualTransactionVirtualImportHelper,
)
from domain.dezimal import Dezimal
from domain.exception.exceptions import EntityNotFound, ManualInvestmentNotFound
from domain.fetch_record import DataSource
from domain.historic import HistoricState, SettleManualInvestmentRequest
from domain.transactions import Transactions, TxType
from domain.use_cases.settle_manual_investment import SettleManualInvestment
from uuid import uuid4


class SettleManualInvestmentImpl(SettleManualInvestment):
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

    async def execute(self, request: SettleManualInvestmentRequest):
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
        maturity = request.maturity or datetime.now(tzlocal())

        existing = await self._historic_port.get_by_manual_key(
            manual_key, fetch_related_txs=True
        )
        existing_id = existing.id if existing else uuid4()
        prior_txs = existing.related_txs if existing else []

        already_repaid = Dezimal(0)
        for tx in prior_txs:
            if tx.type == TxType.REPAYMENT:
                already_repaid += tx.amount

        invested = entry.amount
        entry_pending = getattr(entry, "pending_amount", None)
        if entry_pending is not None:
            outstanding = entry_pending
        else:
            outstanding = invested - already_repaid
        if outstanding < Dezimal(0):
            outstanding = Dezimal(0)
        pending_capital = request.pending_capital or Dezimal(0)
        repaid = outstanding - pending_capital
        if repaid < Dezimal(0):
            repaid = Dezimal(0)

        if request.interests is not None:
            interests = request.interests
        else:
            interests = round(repaid * entry.profitability, 2)

        state = (
            HistoricState.COMPLETED.value
            if pending_capital <= Dezimal(0)
            else HistoricState.DEFAULTED.value
        )

        new_txs = []
        if repaid > Dezimal(0):
            new_txs.append(
                make_investment_tx(
                    entity,
                    entry,
                    request.product_type,
                    TxType.REPAYMENT,
                    repaid,
                    Dezimal(0),
                    Dezimal(0),
                    maturity,
                    ref=settlement_tx_ref(),
                )
            )
        if interests > Dezimal(0):
            new_txs.append(
                make_investment_tx(
                    entity,
                    entry,
                    request.product_type,
                    TxType.INTEREST,
                    interests,
                    request.fees or Dezimal(0),
                    request.retentions or Dezimal(0),
                    maturity,
                    ref=settlement_tx_ref(),
                )
            )

        has_investment_tx = any(tx.type == TxType.INVESTMENT for tx in prior_txs)
        if request.create_investment_tx and not has_investment_tx:
            new_txs.insert(
                0,
                make_investment_tx(
                    entity,
                    entry,
                    request.product_type,
                    TxType.INVESTMENT,
                    invested,
                    Dezimal(0),
                    Dezimal(0),
                    entry.last_invest_date or entry.start,
                ),
            )

        for tx in new_txs:
            self._tx_helper.update_derived_fields(tx)

        related_txs = prior_txs + new_txs

        finalized = ManualHistoricWriter.build_entry(
            entity,
            entry,
            request.product_type,
            entry_id=existing_id,
            state=state,
            effective_maturity=maturity,
            related_txs=related_txs,
            manual_key=manual_key,
            last_tx_date=maturity,
        )

        container = position.products.get(request.product_type)
        container.entries = [e for e in container.entries if e.id != request.entry_id]
        position.id = uuid4()
        position.date = datetime.now(tzlocal())
        position.source = DataSource.MANUAL

        existing_manual = await self._transaction_port.get_by_entity_and_source(
            entity.id, DataSource.MANUAL
        )
        has_transactions = bool(new_txs) or bool(
            existing_manual.account + existing_manual.investment
        )

        async with self._transaction_handler_port.start():
            if new_txs:
                await self._transaction_port.save(Transactions(investment=new_txs))
            await self._snapshot_writer.write(entity, position, compute_loan_refs=False)
            await self._historic_port.upsert(finalized)
            await self._tx_helper.refresh(entity.id, has_transactions=has_transactions)
