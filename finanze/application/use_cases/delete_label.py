from uuid import UUID

from application.ports.label_port import LabelPort
from application.ports.labeling_rule_port import LabelingRulePort
from application.ports.transaction_handler_port import TransactionHandlerPort
from domain.exception.exceptions import LabelNotFound
from domain.use_cases.delete_label import DeleteLabel


class DeleteLabelImpl(DeleteLabel):
    def __init__(
        self,
        label_port: LabelPort,
        labeling_rule_port: LabelingRulePort,
        transaction_handler_port: TransactionHandlerPort,
    ):
        self._label_port = label_port
        self._labeling_rule_port = labeling_rule_port
        self._transaction_handler_port = transaction_handler_port

    async def execute(self, label_id: UUID):
        existing = await self._label_port.get_by_id(label_id)
        if existing is None:
            raise LabelNotFound()

        async with self._transaction_handler_port.start():
            await self._label_port.delete(label_id)
            for rule in await self._labeling_rule_port.get_all():
                if not rule.label_ids:
                    await self._labeling_rule_port.delete(rule.id)
