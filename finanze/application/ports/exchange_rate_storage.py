import abc
from datetime import datetime

from domain.exchange_rate import ExchangeRates


class ExchangeRateStorage(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get(self) -> ExchangeRates:
        raise NotImplementedError

    @abc.abstractmethod
    async def save(self, exchange_rates: ExchangeRates):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_last_saved(self) -> datetime | None:
        raise NotImplementedError
