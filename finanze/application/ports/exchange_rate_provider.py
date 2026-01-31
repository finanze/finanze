import abc

from domain.exchange_rate import ExchangeRates


class ExchangeRateProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_available_currencies(self, **kwargs) -> dict[str, str]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_matrix(self, **kwargs) -> ExchangeRates:
        raise NotImplementedError
