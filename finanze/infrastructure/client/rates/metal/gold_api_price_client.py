import logging
from typing import Optional

import requests
from requests import Timeout

from domain.commodity import COMMODITY_SYMBOLS, CommodityType, WeightUnit
from domain.dezimal import Dezimal
from domain.exchange_rate import CommodityExchangeRate


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

    def get_price(self, commodity: CommodityType) -> Optional[CommodityExchangeRate]:
        if commodity not in self.SUPPORTED_COMMODITIES:
            raise ValueError(f"Unsupported commodity type: {commodity}")

        return self._fetch_price(COMMODITY_SYMBOLS.get(commodity).upper())

    def _fetch_price(self, symbol: str) -> Optional[CommodityExchangeRate]:
        url = f"{self.BASE_URL}/{symbol}"
        try:
            data = self._fetch(url)
        except Timeout as e:
            self._log.error(f"Timeout fetching price for {symbol}: {e}")
            return None

        return CommodityExchangeRate(
            unit=WeightUnit.TROY_OUNCE,
            currency="USD",
            price=Dezimal(str(data["price"])),
        )

    def _fetch(self, url: str) -> dict:
        response = requests.get(url, timeout=self.TIMEOUT)
        if response.ok:
            return response.json()

        self._log.error("Error Response Body:" + response.text)
        response.raise_for_status()
        return {}
