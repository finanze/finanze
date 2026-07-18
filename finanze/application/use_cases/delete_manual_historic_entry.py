from application.ports.historic_port import HistoricPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_port import TransactionPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from application.use_cases.manual_transaction_common import (
    ManualTransactionVirtualImportHelper,
)
from application.use_cases.manual_historic_common import is_settlement_tx
from domain.exception.exceptions import ManualHistoricEntryNotFound
from domain.fetch_record import DataSource
from domain.historic import (
    DeleteManualHistoricEntryRequest,
    HistoricTxDeletion,
)
from domain.use_cases.delete_manual_historic_entry import DeleteManualHistoricEntry


class DeleteManualHistoricEntryImpl(DeleteManualHistoricEntry):
    def __init__(
        self,
        historic_port: HistoricPort,
        transaction_port: TransactionPort,
        virtual_import_registry: VirtualImportRegistry,
        transaction_handler_port: TransactionHandlerPort,
    ):
        self._historic_port = historic_port
        self._transaction_port = transaction_port
        self._transaction_handler_port = transaction_handler_port
        self._tx_helper = ManualTransactionVirtualImportHelper(virtual_import_registry)

    async def execute(self, request: DeleteManualHistoricEntryRequest):
        entry = await self._historic_port.get_by_id(
            request.entry_id, fetch_related_txs=True
        )
        if entry is None or entry.source != DataSource.MANUAL:
            raise ManualHistoricEntryNotFound(request.entry_id)

        entity_id = entry.entity.id
        txs_to_delete = self._select_txs(entry, request.tx_deletion)

        async with self._transaction_handler_port.start():
            for tx in txs_to_delete:
                await self._transaction_port.delete_by_id(tx.id)

            await self._historic_port.delete_by_id(entry.id)

            if txs_to_delete:
                manual_remaining = (
                    await self._transaction_port.get_by_entity_and_source(
                        entity_id, DataSource.MANUAL
                    )
                )
                has_transactions = bool(
                    manual_remaining.account + manual_remaining.investment
                )
                await self._tx_helper.refresh(
                    entity_id, has_transactions=has_transactions
                )

    @staticmethod
    def _select_txs(entry, mode: HistoricTxDeletion):
        related = entry.related_txs or []
        if mode == HistoricTxDeletion.ALL:
            return list(related)
        if mode == HistoricTxDeletion.SETTLEMENT:
            tagged = [tx for tx in related if is_settlement_tx(tx)]
            if tagged:
                return tagged
            if entry.effective_maturity:
                maturity_day = entry.effective_maturity.date()
                return [tx for tx in related if tx.date.date() == maturity_day]
        return []
