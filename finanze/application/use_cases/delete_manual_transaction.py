from uuid import UUID

from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_port import TransactionPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from application.use_cases.manual_transaction_common import (
    ManualTransactionVirtualImportHelper,
)
from domain.exception.exceptions import TransactionNotFound
from domain.fetch_record import DataSource
from domain.use_cases.delete_manual_transaction import DeleteManualTransaction


class DeleteManualTransactionImpl(DeleteManualTransaction, AtomicUCMixin):
    def __init__(
        self,
        transaction_port: TransactionPort,
        virtual_import_registry: VirtualImportRegistry,
        transaction_handler_port: TransactionHandlerPort,
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)
        self._transaction_port = transaction_port
        self._helper = ManualTransactionVirtualImportHelper(virtual_import_registry)

    async def execute(self, tx_id: UUID):
        existing = await self._transaction_port.get_by_id(tx_id)
        if existing is None:
            raise TransactionNotFound(tx_id)

        if existing.source != DataSource.MANUAL:
            raise TransactionNotFound(tx_id)

        entity_id = existing.entity.id

        await self._transaction_port.delete_by_id(tx_id)

        manual_remaining = await self._transaction_port.get_by_entity_and_source(
            entity_id, DataSource.MANUAL
        )

        has_transactions = bool(manual_remaining.account + manual_remaining.investment)

        await self._helper.refresh(entity_id, has_transactions=has_transactions)
