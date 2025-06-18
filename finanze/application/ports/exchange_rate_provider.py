import abc

from domain.exchange_rate import ExchangeRates


class ExchangeRateProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def get_available_currencies(self) -> dict[str, str]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_matrix(self) -> ExchangeRates:
        raise NotImplementedError
