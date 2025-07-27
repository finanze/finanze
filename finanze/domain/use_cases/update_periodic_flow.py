import abc

from domain.earnings_expenses import PeriodicFlow


class UpdatePeriodicFlow(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, flow: PeriodicFlow):
        raise NotImplementedError
