from datetime import datetime
from uuid import uuid4

from dateutil.tz import tzlocal

from application.ports.historic_port import HistoricPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_port import TransactionPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from application.use_cases.manual_historic_common import (
    ManualHistoricWriter,
    is_settlement_tx,
    load_manual_position,
)
from application.use_cases.manual_position_snapshot import ManualPositionSnapshotWriter
from application.use_cases.manual_transaction_common import (
    ManualTransactionVirtualImportHelper,
)
from domain.dezimal import Dezimal
from domain.exception.exceptions import (
    ManualHistoricEntryNotFinal,
    ManualHistoricEntryNotFound,
    ManualInvestmentNotFound,
)
from domain.fetch_record import DataSource
from domain.global_position import (
    FactoringDetail,
    FactoringInvestments,
    ProductType,
    RealEstateCFDetail,
    RealEstateCFInvestments,
)
from domain.historic import (
    FINAL_HISTORIC_STATES,
    FactoringEntry,
    RealEstateCFEntry,
    UnsettleManualInvestmentRequest,
)
from domain.transactions import TxType
from domain.use_cases.unsettle_manual_investment import UnsettleManualInvestment

RESTORED_STATE = "FUNDED"


class UnsettleManualInvestmentImpl(UnsettleManualInvestment):
    def __init__(
        self,
        historic_port: HistoricPort,
        position_port: PositionPort,
        transaction_port: TransactionPort,
        virtual_import_registry: VirtualImportRegistry,
        snapshot_writer: ManualPositionSnapshotWriter,
        transaction_handler_port: TransactionHandlerPort,
    ):
        self._historic_port = historic_port
        self._position_port = position_port
        self._transaction_port = transaction_port
        self._virtual_import_registry = virtual_import_registry
        self._snapshot_writer = snapshot_writer
        self._transaction_handler_port = transaction_handler_port
        self._tx_helper = ManualTransactionVirtualImportHelper(virtual_import_registry)

    async def execute(self, request: UnsettleManualInvestmentRequest):
        entry = await self._historic_port.get_by_id(
            request.entry_id, fetch_related_txs=True
        )
        if entry is None or entry.source != DataSource.MANUAL:
            raise ManualHistoricEntryNotFound(request.entry_id)
        if entry.state not in FINAL_HISTORIC_STATES:
            raise ManualHistoricEntryNotFinal(request.entry_id)

        entity = entry.entity
        product_type = entry.product_type

        related = list(entry.related_txs or [])
        settlement_txs = [tx for tx in related if is_settlement_tx(tx)]
        kept = [tx for tx in related if tx not in settlement_txs]

        repaid = Dezimal(0)
        for tx in kept:
            if tx.type == TxType.REPAYMENT:
                repaid += tx.amount

        detail = self._reconstruct_detail(entry, product_type, repaid)

        position = await load_manual_position(
            self._virtual_import_registry, self._position_port, entity.id
        )
        if position is None:
            raise ManualInvestmentNotFound(request.entry_id)

        container = position.products.get(product_type)
        if container is None:
            container = (
                FactoringInvestments(entries=[])
                if product_type == ProductType.FACTORING
                else RealEstateCFInvestments(entries=[])
            )
            position.products[product_type] = container
        container.entries = list(container.entries) + [detail]

        position.id = uuid4()
        position.date = datetime.now(tzlocal())
        position.source = DataSource.MANUAL

        manual_key = ManualHistoricWriter.manual_key_for(entity.id, detail)
        ongoing = ManualHistoricWriter.build_entry(
            entity,
            detail,
            product_type,
            entry_id=entry.id,
            state=detail.state,
            effective_maturity=None,
            related_txs=kept,
            manual_key=manual_key,
        )

        async with self._transaction_handler_port.start():
            for tx in settlement_txs:
                await self._transaction_port.delete_by_id(tx.id)
            await self._snapshot_writer.write(entity, position, compute_loan_refs=False)
            await self._historic_port.upsert(ongoing)

            manual_remaining = await self._transaction_port.get_by_entity_and_source(
                entity.id, DataSource.MANUAL
            )
            has_transactions = bool(
                manual_remaining.account + manual_remaining.investment
            )
            await self._tx_helper.refresh(entity.id, has_transactions=has_transactions)

    @staticmethod
    def _reconstruct_detail(entry, product_type: ProductType, repaid: Dezimal):
        start = entry.last_invest_date
        if product_type == ProductType.FACTORING and isinstance(entry, FactoringEntry):
            return FactoringDetail(
                id=uuid4(),
                name=entry.name,
                amount=entry.invested,
                currency=entry.currency,
                interest_rate=entry.interest_rate,
                start=start,
                maturity=entry.maturity,
                type=entry.type,
                state=RESTORED_STATE,
                last_invest_date=entry.last_invest_date,
                gross_interest_rate=entry.gross_interest_rate,
                source=DataSource.MANUAL,
            )
        if isinstance(entry, RealEstateCFEntry):
            pending = entry.invested - repaid
            if pending < Dezimal(0):
                pending = Dezimal(0)
            return RealEstateCFDetail(
                id=uuid4(),
                name=entry.name,
                amount=entry.invested,
                pending_amount=pending,
                currency=entry.currency,
                interest_rate=entry.interest_rate,
                start=start,
                maturity=entry.maturity,
                type=entry.type,
                state=RESTORED_STATE,
                business_type=entry.business_type,
                last_invest_date=entry.last_invest_date,
                extended_maturity=entry.extended_maturity,
                source=DataSource.MANUAL,
            )
        raise ManualHistoricEntryNotFound(entry.id)
