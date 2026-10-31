from application.ports.label_port import LabelPort
from application.ports.labeling_rule_port import LabelingRulePort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_label_port import TransactionLabelPort
from application.ports.transaction_labeler import TransactionLabeler
from domain.exception.exceptions import LabelingRuleNotFound, LabelNotFound
from domain.labeling import SavedLabelingRule, SaveLabelingRuleRequest, validate_rule
from domain.use_cases.update_labeling_rule import UpdateLabelingRule


class UpdateLabelingRuleImpl(UpdateLabelingRule):
    def __init__(
        self,
        labeling_rule_port: LabelingRulePort,
        label_port: LabelPort,
        transaction_label_port: TransactionLabelPort,
        transaction_labeler: TransactionLabeler,
        transaction_handler_port: TransactionHandlerPort,
    ):
        self._labeling_rule_port = labeling_rule_port
        self._label_port = label_port
        self._transaction_label_port = transaction_label_port
        self._transaction_labeler = transaction_labeler
        self._transaction_handler_port = transaction_handler_port

    async def execute(self, request: SaveLabelingRuleRequest) -> SavedLabelingRule:
        rule = request.rule
        existing = await self._labeling_rule_port.get_by_id(rule.id)
        if existing is None:
            raise LabelingRuleNotFound()

        rule.name = rule.name.strip() if rule.name and rule.name.strip() else None
        rule.label_ids = list(dict.fromkeys(rule.label_ids))
        rule.kind = existing.kind
        validate_rule(rule)

        known = {label.id for label in await self._label_port.get_all()}
        if any(label_id not in known for label_id in rule.label_ids):
            raise LabelNotFound()

        applied = 0
        async with self._transaction_handler_port.start():
            await self._labeling_rule_port.update(rule)
            if request.apply_to_existing:
                await self._transaction_label_port.delete_by_rule(rule.id)
                applied = await self._transaction_labeler.apply_rule(rule)

        return SavedLabelingRule(rule=rule, applied=applied)
