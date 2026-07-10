import abc
from typing import Optional

from domain.commodity import CommodityType
from domain.exchange_rate import HistoricMetalRates


class HistoricMetalPriceProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_partial_historic_rates(
        self, commodity: CommodityType, **kwargs
    ) -> Optional[HistoricMetalRates]:
        raise NotImplementedError
