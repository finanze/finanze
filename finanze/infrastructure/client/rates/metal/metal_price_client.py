import logging
from typing import Optional

from application.ports.metal_price_provider import MetalPriceProvider
from cachetools import TTLCache
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

        self._price_cache: TTLCache[CommodityType, CommodityExchangeRate] = TTLCache(
            maxsize=10, ttl=self.PRICE_CACHE_TTL
        )
        self._none_cache: TTLCache[CommodityType, Optional[CommodityExchangeRate]] = (
            TTLCache(maxsize=10, ttl=self.NONE_PRICE_CACHE_TTL)
        )

        self._log = logging.getLogger(__name__)

    def get_price(self, commodity: CommodityType) -> Optional[CommodityExchangeRate]:
        if commodity in self._price_cache:
            return self._price_cache[commodity]

        if commodity in self._none_cache:
            return None

        client = self.SYMBOL_MAPPINGS[commodity]
        price = client.get_price(commodity)

        if price is None:
            self._log.error(f"Failed to fetch price for {commodity}, skipping.")
            if commodity in self._price_cache:
                del self._price_cache[commodity]
            self._none_cache[commodity] = None
        else:
            if commodity in self._none_cache:
                del self._none_cache[commodity]
            self._price_cache[commodity] = price

        return price
