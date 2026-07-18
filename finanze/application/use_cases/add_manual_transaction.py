from uuid import UUID, uuid4

from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.entity_port import EntityPort
from application.ports.historic_port import HistoricPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_port import TransactionPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from application.use_cases.manual_transaction_common import (
    ManualTransactionVirtualImportHelper,
)
from domain.exception.exceptions import EntityNotFound
from domain.transactions import AccountTx, BaseInvestmentTx, BaseTx, Transactions
from domain.use_cases.add_manual_transaction import AddManualTransaction

from typing import Optional


class AddManualTransactionImpl(AddManualTransaction, AtomicUCMixin):
    def __init__(
        self,
        entity_port: EntityPort,
        transaction_port: TransactionPort,
        virtual_import_registry: VirtualImportRegistry,
        transaction_handler_port: TransactionHandlerPort,
        historic_port: HistoricPort,
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)
        self._entity_port = entity_port
        self._transaction_port = transaction_port
        self._historic_port = historic_port
        self._helper = ManualTransactionVirtualImportHelper(virtual_import_registry)

    async def execute(
        self, tx: BaseTx, historic_entry_id: Optional[UUID] = None
    ) -> UUID:
        existing_entity = await self._entity_port.get_by_id(tx.entity.id)
        if existing_entity is None:
            raise EntityNotFound(tx.entity.id)

        tx.entity = existing_entity
        tx.id = uuid4()

        tx = self._helper.update_derived_fields(tx)

        if tx.product_type == tx.product_type.ACCOUNT:
            if not isinstance(tx, AccountTx):
                raise ValueError(
                    "ACCOUNT product_type requires AccountTx data structure"
                )
            await self._transaction_port.save(Transactions(account=[tx]))
        else:
            if not isinstance(tx, BaseInvestmentTx):
                raise ValueError(
                    "Investment product_type requires investment tx structure"
                )
            await self._transaction_port.save(Transactions(investment=[tx]))

        if historic_entry_id is not None:
            await self._historic_port.link_txs(historic_entry_id, [tx.id])

        await self._helper.refresh(tx.entity.id, has_transactions=True)

        return tx.id
