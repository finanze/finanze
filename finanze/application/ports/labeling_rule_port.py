import abc
from typing import Optional
from uuid import UUID

from domain.labeling import LabelingRule


class LabelingRulePort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_all(self, enabled_only: bool = False) -> list[LabelingRule]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_id(self, rule_id: UUID) -> Optional[LabelingRule]:
        raise NotImplementedError

    @abc.abstractmethod
    async def save(self, rule: LabelingRule) -> LabelingRule:
        raise NotImplementedError

    @abc.abstractmethod
    async def update(self, rule: LabelingRule):
        raise NotImplementedError

    @abc.abstractmethod
    async def delete(self, rule_id: UUID):
        raise NotImplementedError
