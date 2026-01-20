import logging
from typing import Optional

import httpx
from domain.commodity import COMMODITY_SYMBOLS, CommodityType, WeightUnit
from domain.dezimal import Dezimal
from domain.exchange_rate import CommodityExchangeRate
from infrastructure.client.http.http_session import get_http_session


class GoldApiPriceClient:
    BASE_URL = "https://api.gold-api.com/price"
    TIMEOUT = 3

    SUPPORTED_COMMODITIES = {
        CommodityType.GOLD,
        CommodityType.SILVER,
        CommodityType.PALLADIUM,
    }

    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._session = get_http_session()

    async def get_price(
        self, commodity: CommodityType, timeout: int | None = None
    ) -> Optional[CommodityExchangeRate]:
        if commodity not in self.SUPPORTED_COMMODITIES:
            raise ValueError(f"Unsupported commodity type: {commodity}")

        return await self._fetch_price(
            COMMODITY_SYMBOLS.get(commodity).upper(), timeout or self.TIMEOUT
        )

    async def _fetch_price(
        self, symbol: str, timeout: int
    ) -> Optional[CommodityExchangeRate]:
        url = f"{self.BASE_URL}/{symbol}"
        try:
            data = await self._fetch(url, timeout)
        except (httpx.RequestError, TimeoutError) as e:
            self._log.error(f"Timeout fetching price for {symbol}: {e}")
            return None

        return CommodityExchangeRate(
            unit=WeightUnit.TROY_OUNCE,
            currency="USD",
            price=Dezimal(str(data["price"])),
        )

    async def _fetch(self, url: str, request_timeout: int) -> dict:
        response = await self._session.get(url, timeout=request_timeout)
        if response.ok:
            return await response.json()

        body = await response.text()
        self._log.error("Error Response Body:" + body)
        response.raise_for_status()
        return {}
