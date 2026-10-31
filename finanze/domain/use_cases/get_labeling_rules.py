import abc

from domain.labeling import LabelingRules


class GetLabelingRules(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> LabelingRules:
        raise NotImplementedError
