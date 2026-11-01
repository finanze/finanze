from uuid import UUID

from application.ports.labeling_rule_port import LabelingRulePort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_label_port import TransactionLabelPort
from domain.exception.exceptions import LabelingRuleNotFound
from domain.use_cases.delete_labeling_rule import DeleteLabelingRule


class DeleteLabelingRuleImpl(DeleteLabelingRule):
    def __init__(
        self,
        labeling_rule_port: LabelingRulePort,
        transaction_label_port: TransactionLabelPort,
        transaction_handler_port: TransactionHandlerPort,
    ):
        self._labeling_rule_port = labeling_rule_port
        self._transaction_label_port = transaction_label_port
        self._transaction_handler_port = transaction_handler_port

    async def execute(self, rule_id: UUID):
        existing = await self._labeling_rule_port.get_by_id(rule_id)
        if existing is None:
            raise LabelingRuleNotFound()

        async with self._transaction_handler_port.start():
            await self._transaction_label_port.delete_by_rule(rule_id)
            await self._labeling_rule_port.delete(rule_id)
