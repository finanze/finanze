import abc

from domain.earnings_expenses import PeriodicFlow


class GetPeriodicFlows(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> list[PeriodicFlow]:
        raise NotImplementedError
