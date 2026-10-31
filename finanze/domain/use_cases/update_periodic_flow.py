import abc

from domain.earnings_expenses import PeriodicFlow


class UpdatePeriodicFlow(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, flow: PeriodicFlow, *, label_id_provided: bool = True):
        raise NotImplementedError
