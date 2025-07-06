from application.ports.metal_price_provider import MetalPriceProvider
from cachetools import TTLCache, cached
from domain.commodity import CommodityType
from domain.exchange_rate import CommodityExchangeRate
from infrastructure.client.rates.metal.gold_api_price_client import GoldApiPriceClient
from infrastructure.client.rates.metal.rmint_api_price_client import RMintApiPriceClient


class MetalPriceClient(MetalPriceProvider):
    PRICE_CACHE_TTL = 20 * 60

    def __init__(self):
        self._gold_api_price_client = GoldApiPriceClient()
        self._rmint_api_price_client = RMintApiPriceClient()

        self.SYMBOL_MAPPINGS = {
            CommodityType.GOLD: self._gold_api_price_client,
            CommodityType.SILVER: self._gold_api_price_client,
            CommodityType.PLATINUM: self._rmint_api_price_client,
            CommodityType.PALLADIUM: self._gold_api_price_client,
        }

    @cached(TTLCache(maxsize=10, ttl=PRICE_CACHE_TTL))
    def get_price(self, commodity: CommodityType) -> CommodityExchangeRate:
        client = self.SYMBOL_MAPPINGS[commodity]
        return client.get_price(commodity)
