from application.ports.labeling_rule_port import LabelingRulePort
from domain.labeling import LabelingRules
from domain.use_cases.get_labeling_rules import GetLabelingRules


class GetLabelingRulesImpl(GetLabelingRules):
    def __init__(self, labeling_rule_port: LabelingRulePort):
        self._labeling_rule_port = labeling_rule_port

    async def execute(self) -> LabelingRules:
        return LabelingRules(rules=await self._labeling_rule_port.get_all())
