import abc
from typing import Optional

from domain.commodity import CommodityType
from domain.exchange_rate import CommodityExchangeRate


class MetalPriceProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_price(
        self, commodity: CommodityType, **kwargs
    ) -> Optional[CommodityExchangeRate]:
        raise NotImplementedError
