from application.ports.label_port import LabelPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_label_port import TransactionLabelPort
from application.ports.transaction_labeler import TransactionLabeler
from application.ports.transaction_port import TransactionPort
from domain.exception.exceptions import LabelNotFound, TransactionNotFound
from domain.labeling import UpdateTransactionLabelsRequest
from domain.transactions import AccountTx, AccountTxSelection, LabelOrigin, TxLabel
from domain.use_cases.update_transaction_labels import UpdateTransactionLabels


class UpdateTransactionLabelsImpl(UpdateTransactionLabels):
    def __init__(
        self,
        transaction_port: TransactionPort,
        transaction_label_port: TransactionLabelPort,
        label_port: LabelPort,
        transaction_labeler: TransactionLabeler,
        transaction_handler_port: TransactionHandlerPort,
    ):
        self._transaction_port = transaction_port
        self._transaction_label_port = transaction_label_port
        self._label_port = label_port
        self._transaction_labeler = transaction_labeler
        self._transaction_handler_port = transaction_handler_port

    async def execute(self, request: UpdateTransactionLabelsRequest):
        tx = await self._transaction_port.get_by_id(request.tx_id)
        if not isinstance(tx, AccountTx):
            raise TransactionNotFound()

        label_ids = list(dict.fromkeys(request.label_ids))
        known = {label.id for label in await self._label_port.get_all()}
        if any(label_id not in known for label_id in label_ids):
            raise LabelNotFound()

        pair = tx.transfer_pair if request.unpair else None
        locked = (
            request.locked
            or (request.unlink and tx.linked_tx is not None)
            or pair is not None
        )

        async with self._transaction_handler_port.start():
            await self._transaction_label_port.delete([tx.id])
            await self._transaction_label_port.add(
                tx.id,
                [
                    TxLabel(label_id=label_id, origin=LabelOrigin.MANUAL)
                    for label_id in label_ids
                ],
            )
            if request.unlink and tx.linked_tx:
                await self._transaction_label_port.set_linked_tx(tx.id, None)
            if pair:
                await self._transaction_label_port.delete_transfer_pair(tx.id)
            await self._transaction_label_port.set_locked([tx.id], locked)

            if not locked:
                await self._transaction_labeler.classify(
                    AccountTxSelection(ids=[tx.id])
                )
            if pair:
                await self._transaction_labeler.classify(
                    AccountTxSelection(ids=[pair.tx_id])
                )
