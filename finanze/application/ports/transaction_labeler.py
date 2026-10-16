import abc

from domain.labeling import LabelingResult, LabelingRule, LabelingTrigger
from domain.transactions import AccountTxSelection


class TransactionLabeler(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def classify(self, selection: AccountTxSelection) -> LabelingResult:
        raise NotImplementedError

    @abc.abstractmethod
    async def link_settlements(self, selection: AccountTxSelection) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    async def classify_external(
        self,
        selection: AccountTxSelection,
        trigger: LabelingTrigger,
        retry_unmatched: bool = False,
    ) -> LabelingResult:
        raise NotImplementedError

    @abc.abstractmethod
    async def apply_rule(self, rule: LabelingRule) -> int:
        raise NotImplementedError
