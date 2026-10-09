import abc

from domain.labeling import LabelingRulePreview, LabelingRulePreviewRequest


class PreviewLabelingRule(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: LabelingRulePreviewRequest) -> LabelingRulePreview:
        raise NotImplementedError
