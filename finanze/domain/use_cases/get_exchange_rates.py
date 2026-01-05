import abc

from domain.exchange_rate import ExchangeRates


class GetExchangeRates(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, initial_load: bool = False) -> ExchangeRates:
        pass
