from application.ports.label_port import LabelPort
from application.ports.labeling_rule_port import LabelingRulePort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_labeler import TransactionLabeler
from domain.exception.exceptions import LabelNotFound
from domain.labeling import SavedLabelingRule, SaveLabelingRuleRequest, validate_rule
from domain.use_cases.create_labeling_rule import CreateLabelingRule


class CreateLabelingRuleImpl(CreateLabelingRule):
    def __init__(
        self,
        labeling_rule_port: LabelingRulePort,
        label_port: LabelPort,
        transaction_labeler: TransactionLabeler,
        transaction_handler_port: TransactionHandlerPort,
    ):
        self._labeling_rule_port = labeling_rule_port
        self._label_port = label_port
        self._transaction_labeler = transaction_labeler
        self._transaction_handler_port = transaction_handler_port

    async def execute(self, request: SaveLabelingRuleRequest) -> SavedLabelingRule:
        rule = request.rule
        rule.id = None
        rule.name = rule.name.strip() if rule.name and rule.name.strip() else None
        rule.label_ids = list(dict.fromkeys(rule.label_ids))
        validate_rule(rule)

        known = {label.id for label in await self._label_port.get_all()}
        if any(label_id not in known for label_id in rule.label_ids):
            raise LabelNotFound()

        applied = 0
        async with self._transaction_handler_port.start():
            rule = await self._labeling_rule_port.save(rule)
            if request.apply_to_existing:
                applied = await self._transaction_labeler.apply_rule(rule)

        return SavedLabelingRule(rule=rule, applied=applied)
