import logging
from datetime import date
from typing import Optional

import httpx
from aiocache import Cache

from application.ports.historic_metal_price_provider import HistoricMetalPriceProvider
from domain.commodity import COMMODITY_SYMBOLS, CommodityType, WeightUnit
from domain.dezimal import Dezimal
from domain.exchange_rate import HistoricMetalRates
from infrastructure.client.http.http_session import get_http_session


class HistoricMetalPriceClient(HistoricMetalPriceProvider):
    BASE_URL = "https://static.finanze.me/rates/metals"
    TIMEOUT = 10
    CACHE_TTL = 12 * 60 * 60  # 12 hours; the dataset is historical and static

    SUPPORTED_COMMODITIES = {
        CommodityType.GOLD,
        CommodityType.SILVER,
        CommodityType.PLATINUM,
        CommodityType.PALLADIUM,
    }

    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._session = get_http_session()
        self._cache = Cache(Cache.MEMORY)

    async def get_partial_historic_rates(
        self, commodity: CommodityType, **kwargs
    ) -> Optional[HistoricMetalRates]:
        if commodity not in self.SUPPORTED_COMMODITIES:
            raise ValueError(f"Unsupported commodity type: {commodity}")

        cache_key = self._cache_key(commodity)
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        symbol = COMMODITY_SYMBOLS[commodity].lower()
        url = f"{self.BASE_URL}/{symbol}.json"
        try:
            response = await self._session.get(
                url, timeout=kwargs.get("timeout") or self.TIMEOUT
            )
            if not response.ok:
                body = await response.text()
                self._log.error(
                    f"Error fetching historic rates for {commodity}: {body}"
                )
                return None
            raw = await response.json()
        except (httpx.RequestError, TimeoutError) as e:
            self._log.error(f"Failed fetching historic rates for {commodity}: {e}")
            return None

        rates = self._build(raw)
        if rates is not None:
            await self._cache.set(cache_key, rates, ttl=self.CACHE_TTL)
        return rates

    def _build(self, raw: dict) -> Optional[HistoricMetalRates]:
        if not raw:
            return None

        ordered = sorted(raw.items())
        days: list[date] = []
        series: dict[str, list[Dezimal]] = {}
        for day_str, by_currency in ordered:
            days.append(date.fromisoformat(day_str))
            for currency, value in by_currency.items():
                series.setdefault(currency, []).append(Dezimal(str(value)))

        return HistoricMetalRates(
            unit=WeightUnit.TROY_OUNCE,
            days=tuple(days),
            prices={currency: tuple(values) for currency, values in series.items()},
        )

    @staticmethod
    def _cache_key(commodity: CommodityType) -> str:
        return f"historic_metal_rates:{commodity.value}"
