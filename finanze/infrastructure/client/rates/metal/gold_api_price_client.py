import logging
from typing import Optional

import requests
from domain.commodity import COMMODITY_SYMBOLS, CommodityType, WeightUnit
from domain.dezimal import Dezimal
from domain.exchange_rate import CommodityExchangeRate
from requests import Timeout


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

    def get_price(
        self, commodity: CommodityType, timeout: int | None = None
    ) -> Optional[CommodityExchangeRate]:
        if commodity not in self.SUPPORTED_COMMODITIES:
            raise ValueError(f"Unsupported commodity type: {commodity}")

        return self._fetch_price(
            COMMODITY_SYMBOLS.get(commodity).upper(), timeout or self.TIMEOUT
        )

    def _fetch_price(
        self, symbol: str, timeout: int
    ) -> Optional[CommodityExchangeRate]:
        url = f"{self.BASE_URL}/{symbol}"
        try:
            data = self._fetch(url, timeout)
        except Timeout as e:
            self._log.error(f"Timeout fetching price for {symbol}: {e}")
            return None

        return CommodityExchangeRate(
            unit=WeightUnit.TROY_OUNCE,
            currency="USD",
            price=Dezimal(str(data["price"])),
        )

    def _fetch(self, url: str, timeout: int) -> dict:
        response = requests.get(url, timeout=timeout)
        if response.ok:
            return response.json()

        self._log.error("Error Response Body:" + response.text)
        response.raise_for_status()
        return {}
