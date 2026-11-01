from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_label_port import TransactionLabelPort
from application.ports.transaction_labeler import TransactionLabeler
from application.ports.transaction_port import TransactionPort
from domain.labeling import (
    LABELABLE_TX_TYPES,
    LabelingTrigger,
    RelabelRequest,
    RelabelResult,
)
from domain.transactions import AccountTxSelection, LabelOrigin
from domain.use_cases.relabel_transactions import RelabelTransactions

DEFAULT_RELABEL_ORIGINS = [LabelOrigin.RULE, LabelOrigin.EXTERNAL]


class RelabelTransactionsImpl(RelabelTransactions):
    def __init__(
        self,
        transaction_port: TransactionPort,
        transaction_label_port: TransactionLabelPort,
        transaction_labeler: TransactionLabeler,
        transaction_handler_port: TransactionHandlerPort,
    ):
        self._transaction_port = transaction_port
        self._transaction_label_port = transaction_label_port
        self._transaction_labeler = transaction_labeler
        self._transaction_handler_port = transaction_handler_port

    async def execute(self, request: RelabelRequest) -> RelabelResult:
        if (
            request.from_date
            and request.to_date
            and request.from_date > request.to_date
        ):
            raise ValueError("Start date is after end date")

        selection = AccountTxSelection(
            from_date=request.from_date,
            to_date=request.to_date,
            entities=request.entities,
            types=list(LABELABLE_TX_TYPES),
            with_labels=request.with_labels,
            without_labels=request.without_labels,
            unlabeled_only=request.unlabeled_only,
            include_locked=False,
            include_linked=False,
        )

        if request.dry_run:
            return RelabelResult(
                matched=await self._transaction_port.count_account_txs(selection)
            )

        txs = await self._transaction_port.get_account_txs(selection)
        ids = [tx.id for tx in txs]
        if not ids:
            return RelabelResult(matched=0)

        origins = request.origins or DEFAULT_RELABEL_ORIGINS
        async with self._transaction_handler_port.start():
            await self._transaction_label_port.delete(ids, origins)
            result = await self._transaction_labeler.classify(
                AccountTxSelection(ids=ids)
            )

        external = None
        if request.include_external:
            external = await self._transaction_labeler.classify_external(
                AccountTxSelection(ids=ids),
                LabelingTrigger.MANUAL,
                retry_unmatched=request.retry_external_unmatched,
            )

        return RelabelResult(matched=len(ids), result=result, external=external)
