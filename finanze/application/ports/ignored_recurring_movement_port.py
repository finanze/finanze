import abc
from uuid import UUID

from domain.cashflow import IgnoredRecurringMovement


class IgnoredRecurringMovementPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_all(self) -> list[IgnoredRecurringMovement]:
        raise NotImplementedError

    @abc.abstractmethod
    async def save(
        self, movement: IgnoredRecurringMovement
    ) -> IgnoredRecurringMovement:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete(self, ignored_id: UUID):
        raise NotImplementedError
