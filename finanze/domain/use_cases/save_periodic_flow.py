import abc

from domain.earnings_expenses import PeriodicFlow


class SavePeriodicFlow(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, flow: PeriodicFlow):
        raise NotImplementedError
