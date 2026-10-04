from uuid import UUID, uuid4

from application.ports.entity_port import EntityPort
from application.ports.historic_port import HistoricPort
from application.ports.label_port import LabelPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_label_port import TransactionLabelPort
from application.ports.transaction_labeler import TransactionLabeler
from application.ports.transaction_port import TransactionPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from application.use_cases.manual_transaction_common import (
    ManualTransactionVirtualImportHelper,
)
from domain.exception.exceptions import EntityNotFound, LabelNotFound
from domain.global_position import ProductType
from domain.labeling import LabelingTrigger
from domain.settlement import settlement_window
from domain.transactions import (
    AccountTx,
    AccountTxSelection,
    AddManualTransactionRequest,
    BaseInvestmentTx,
    BaseTx,
    Transactions,
)
from domain.use_cases.add_manual_transaction import AddManualTransaction


class AddManualTransactionImpl(AddManualTransaction):
    def __init__(
        self,
        entity_port: EntityPort,
        transaction_port: TransactionPort,
        virtual_import_registry: VirtualImportRegistry,
        transaction_handler_port: TransactionHandlerPort,
        historic_port: HistoricPort,
        label_port: LabelPort,
        transaction_label_port: TransactionLabelPort,
        transaction_labeler: TransactionLabeler,
    ):
        self._entity_port = entity_port
        self._transaction_port = transaction_port
        self._transaction_handler_port = transaction_handler_port
        self._historic_port = historic_port
        self._label_port = label_port
        self._transaction_label_port = transaction_label_port
        self._transaction_labeler = transaction_labeler
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

        await self._validate_labels(account_txs)

        async with self._transaction_handler_port.start():
            if account_txs:
                await self._transaction_port.save(Transactions(account=account_txs))
                for tx in account_txs:
                    if tx.labels:
                        await self._transaction_label_port.add(tx.id, tx.labels)
            if investment_txs:
                await self._transaction_port.save(
                    Transactions(investment=investment_txs)
                )

            if request.historic_entry_id is not None:
                await self._historic_port.link_txs(
                    request.historic_entry_id, [item.id for item in resolved]
                )

            if account_txs:
                await self._transaction_labeler.classify(
                    AccountTxSelection(ids=[tx.id for tx in account_txs])
                )
            if investment_txs:
                await self._transaction_labeler.link_settlements(
                    settlement_window(investment_txs)
                )

            for entity_id in {item.entity.id for item in resolved}:
                await self._helper.refresh(entity_id, has_transactions=True)

        if account_txs:
            await self._transaction_labeler.classify_external(
                AccountTxSelection(ids=[tx.id for tx in account_txs]),
                LabelingTrigger.AUTO,
            )

        return resolved[0].id

    async def _validate_labels(self, account_txs: list[AccountTx]):
        requested = {
            label.label_id for tx in account_txs for label in (tx.labels or [])
        }
        if not requested:
            return
        known = {label.id for label in await self._label_port.get_all()}
        if not requested.issubset(known):
            raise LabelNotFound()
