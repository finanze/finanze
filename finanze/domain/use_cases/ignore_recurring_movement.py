import abc

from domain.cashflow import IgnoredRecurringMovement


class IgnoreRecurringMovement(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(
        self, movement: IgnoredRecurringMovement
    ) -> IgnoredRecurringMovement:
        raise NotImplementedError
