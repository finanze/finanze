import abc

from domain.labeling import SavedLabelingRule, SaveLabelingRuleRequest


class CreateLabelingRule(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: SaveLabelingRuleRequest) -> SavedLabelingRule:
        raise NotImplementedError
