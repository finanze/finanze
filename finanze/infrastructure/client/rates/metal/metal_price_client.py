import logging
from typing import Optional

from aiocache import Cache

from application.ports.metal_price_provider import MetalPriceProvider
from domain.commodity import CommodityType
from domain.exchange_rate import CommodityExchangeRate
from infrastructure.client.rates.metal.gold_api_price_client import GoldApiPriceClient
from infrastructure.client.rates.metal.rmint_api_price_client import RMintApiPriceClient


class MetalPriceClient(MetalPriceProvider):
    PRICE_CACHE_TTL = 20 * 60  # 20 minutes
    NONE_PRICE_CACHE_TTL = 30  # 30 seconds for missing prices

    def __init__(self):
        self._gold_api_price_client = GoldApiPriceClient()
        self._rmint_api_price_client = RMintApiPriceClient()

        self.SYMBOL_MAPPINGS = {
            CommodityType.GOLD: self._gold_api_price_client,
            CommodityType.SILVER: self._gold_api_price_client,
            CommodityType.PLATINUM: self._rmint_api_price_client,
            CommodityType.PALLADIUM: self._gold_api_price_client,
        }

        self._price_cache = Cache(Cache.MEMORY)
        self._none_cache = Cache(Cache.MEMORY)

        self._log = logging.getLogger(__name__)

    def _price_cache_key(self, commodity: CommodityType) -> str:
        return f"metal_price:{commodity.value}"

    def _none_cache_key(self, commodity: CommodityType) -> str:
        return f"metal_price_none:{commodity.value}"

    async def get_price(
        self, commodity: CommodityType, **kwargs
    ) -> Optional[CommodityExchangeRate]:
        price_key = self._price_cache_key(commodity)
        none_key = self._none_cache_key(commodity)

        cached_price = await self._price_cache.get(price_key)
        if cached_price is not None:
            return cached_price

        cached_none = await self._none_cache.get(none_key)
        if cached_none is not None:
            return None

        timeout = kwargs.get("timeout", None)
        client = self.SYMBOL_MAPPINGS[commodity]
        price = await client.get_price(commodity, timeout)

        if price is None:
            self._log.error(f"Failed to fetch price for {commodity}, skipping.")
            await self._price_cache.delete(price_key)
            await self._none_cache.set(none_key, True, ttl=self.NONE_PRICE_CACHE_TTL)
        else:
            await self._none_cache.delete(none_key)
            await self._price_cache.set(price_key, price, ttl=self.PRICE_CACHE_TTL)

        return price
