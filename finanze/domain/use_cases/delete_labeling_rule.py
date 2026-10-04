import abc
from uuid import UUID


class DeleteLabelingRule(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, rule_id: UUID):
        raise NotImplementedError
