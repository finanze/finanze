import abc

from domain.exchange_rate import ExchangeRates


class GetExchangeRates(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(
        self, initial_load: bool = False, cached: bool = False
    ) -> ExchangeRates:
        pass
