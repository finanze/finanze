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
from domain.global_position import ProductType
from domain.transactions import (
    AccountTx,
    AddManualTransactionRequest,
    BaseInvestmentTx,
    BaseTx,
    Transactions,
)
from domain.use_cases.add_manual_transaction import AddManualTransaction


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

    async def execute(self, request: AddManualTransactionRequest) -> UUID:
        txs = request.txs
        if not txs:
            raise ValueError("At least one transaction is required")

        resolved: list[BaseTx] = []
        for item in txs:
            existing_entity = await self._entity_port.get_by_id(item.entity.id)
            if existing_entity is None:
                raise EntityNotFound(item.entity.id)

            item.entity = existing_entity
            item.id = uuid4()
            resolved.append(self._helper.update_derived_fields(item))

        account_txs: list[AccountTx] = []
        investment_txs: list[BaseInvestmentTx] = []
        for item in resolved:
            if item.product_type == ProductType.ACCOUNT:
                if not isinstance(item, AccountTx):
                    raise ValueError(
                        "ACCOUNT product_type requires AccountTx data structure"
                    )
                account_txs.append(item)
            else:
                if not isinstance(item, BaseInvestmentTx):
                    raise ValueError(
                        "Investment product_type requires investment tx structure"
                    )
                investment_txs.append(item)

        if account_txs:
            await self._transaction_port.save(Transactions(account=account_txs))
        if investment_txs:
            await self._transaction_port.save(Transactions(investment=investment_txs))

        if request.historic_entry_id is not None:
            await self._historic_port.link_txs(
                request.historic_entry_id, [item.id for item in resolved]
            )

        for entity_id in {item.entity.id for item in resolved}:
            await self._helper.refresh(entity_id, has_transactions=True)

        return resolved[0].id
