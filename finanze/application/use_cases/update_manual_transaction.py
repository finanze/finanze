from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.entity_port import EntityPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_port import TransactionPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from application.use_cases.manual_transaction_common import (
    ManualTransactionVirtualImportHelper,
)
from domain.exception.exceptions import EntityNotFound, TransactionNotFound
from domain.fetch_record import DataSource
from domain.transactions import AccountTx, BaseInvestmentTx, BaseTx, Transactions
from domain.use_cases.update_manual_transaction import UpdateManualTransaction


class UpdateManualTransactionImpl(UpdateManualTransaction, AtomicUCMixin):
    def __init__(
        self,
        entity_port: EntityPort,
        transaction_port: TransactionPort,
        virtual_import_registry: VirtualImportRegistry,
        transaction_handler_port: TransactionHandlerPort,
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)
        self._entity_port = entity_port
        self._transaction_port = transaction_port
        self._helper = ManualTransactionVirtualImportHelper(virtual_import_registry)

    async def execute(self, tx: BaseTx):
        if tx.id is None:
            raise ValueError("Transaction ID required for update")

        existing = self._transaction_port.get_by_id(tx.id)
        if existing is None:
            raise TransactionNotFound(tx.id)

        if existing.source != DataSource.MANUAL:
            raise TransactionNotFound(tx.id)

        tx.entity.id = existing.entity.id
        tx.product_type = existing.product_type

        real_entity = self._entity_port.get_by_id(tx.entity.id)
        if real_entity is None:
            raise EntityNotFound(tx.entity.id)
        tx.entity = real_entity

        tx = self._helper.update_derived_fields(tx)

        self._transaction_port.delete_by_id(tx.id)

        if tx.product_type == tx.product_type.ACCOUNT:
            if not isinstance(tx, AccountTx):
                raise ValueError(
                    "ACCOUNT product_type requires AccountTx data structure"
                )
            self._transaction_port.save(Transactions(account=[tx]))
        else:
            if not isinstance(tx, BaseInvestmentTx):
                raise ValueError(
                    "ACCOUNT product_type requires AccountTx data structure"
                )
            self._transaction_port.save(Transactions(investment=[tx]))

        self._helper.refresh(tx.entity.id, has_transactions=True)
