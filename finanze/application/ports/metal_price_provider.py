import abc
from typing import Optional

from domain.commodity import CommodityType
from domain.exchange_rate import CommodityExchangeRate, HistoricMetalRates


class MetalPriceProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_price(
        self, commodity: CommodityType, **kwargs
    ) -> Optional[CommodityExchangeRate]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_partial_historic_rates(
        self, commodity: CommodityType, **kwargs
    ) -> Optional[HistoricMetalRates]:
        raise NotImplementedError
