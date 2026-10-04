from application.ports.entity_port import EntityPort
from application.ports.label_port import LabelPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_label_port import TransactionLabelPort
from application.ports.transaction_labeler import TransactionLabeler
from application.ports.transaction_port import TransactionPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from application.use_cases.manual_transaction_common import (
    ManualTransactionVirtualImportHelper,
)
from domain.exception.exceptions import (
    EntityNotFound,
    LabelNotFound,
    TransactionNotFound,
)
from domain.fetch_record import DataSource
from domain.labeling import LabelingTrigger
from domain.settlement import settlement_window
from domain.transactions import (
    AccountTx,
    AccountTxSelection,
    BaseInvestmentTx,
    BaseTx,
    Transactions,
    TxClassification,
)
from domain.use_cases.update_manual_transaction import UpdateManualTransaction


class UpdateManualTransactionImpl(UpdateManualTransaction):
    def __init__(
        self,
        entity_port: EntityPort,
        transaction_port: TransactionPort,
        virtual_import_registry: VirtualImportRegistry,
        transaction_handler_port: TransactionHandlerPort,
        label_port: LabelPort,
        transaction_label_port: TransactionLabelPort,
        transaction_labeler: TransactionLabeler,
    ):
        self._entity_port = entity_port
        self._transaction_port = transaction_port
        self._transaction_handler_port = transaction_handler_port
        self._label_port = label_port
        self._transaction_label_port = transaction_label_port
        self._transaction_labeler = transaction_labeler
        self._helper = ManualTransactionVirtualImportHelper(virtual_import_registry)

    async def execute(self, tx: BaseTx):
        if tx.id is None:
            raise ValueError("Transaction ID required for update")

        existing = await self._transaction_port.get_by_id(tx.id)
        if existing is None:
            raise TransactionNotFound(tx.id)

        if existing.source != DataSource.MANUAL:
            raise TransactionNotFound(tx.id)

        tx.entity.id = existing.entity.id
        tx.product_type = existing.product_type

        real_entity = await self._entity_port.get_by_id(tx.entity.id)
        if real_entity is None:
            raise EntityNotFound(tx.entity.id)
        tx.entity = real_entity

        tx = self._helper.update_derived_fields(tx)

        is_account = tx.product_type == tx.product_type.ACCOUNT
        if is_account:
            if not isinstance(tx, AccountTx):
                raise ValueError(
                    "ACCOUNT product_type requires AccountTx data structure"
                )
            await self._validate_labels(tx)
        elif not isinstance(tx, BaseInvestmentTx):
            raise ValueError("ACCOUNT product_type requires AccountTx data structure")

        async with self._transaction_handler_port.start():
            await self._transaction_port.delete_by_id(tx.id)

            if is_account:
                await self._transaction_port.save(Transactions(account=[tx]))
                await self._restore_classification(tx, existing)
                await self._transaction_labeler.classify(
                    AccountTxSelection(ids=[tx.id])
                )
            else:
                await self._transaction_port.save(Transactions(investment=[tx]))
                await self._transaction_labeler.link_settlements(
                    settlement_window([tx])
                )

            await self._helper.refresh(tx.entity.id, has_transactions=True)

        if is_account:
            await self._transaction_labeler.classify_external(
                AccountTxSelection(ids=[tx.id]), LabelingTrigger.AUTO
            )

    async def _restore_classification(self, tx: AccountTx, existing: BaseTx):
        if tx.labels is not None:
            await self._transaction_label_port.add(tx.id, tx.labels)
            return

        if not isinstance(existing, AccountTx):
            return

        await self._transaction_label_port.restore(
            {
                tx.id: TxClassification(
                    labels=existing.labels or [],
                    locked=existing.labels_locked,
                    linked_tx=existing.linked_tx if existing.labels_locked else None,
                    transfer_pair=existing.transfer_pair
                    if existing.labels_locked
                    else None,
                )
            }
        )

    async def _validate_labels(self, tx: AccountTx):
        requested = {label.label_id for label in tx.labels or []}
        if not requested:
            return
        known = {label.id for label in await self._label_port.get_all()}
        if not requested.issubset(known):
            raise LabelNotFound()
