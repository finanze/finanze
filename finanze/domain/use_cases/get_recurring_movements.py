import abc

from domain.cashflow import RecurringMovements, RecurringMovementsQuery


class GetRecurringMovements(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, query: RecurringMovementsQuery) -> RecurringMovements:
        raise NotImplementedError
