import abc

from domain.fiscal_year_simulation import FiscalYearSimulation


class FiscalYear(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def execute(self, year: int) -> FiscalYearSimulation:
        raise NotImplementedError
