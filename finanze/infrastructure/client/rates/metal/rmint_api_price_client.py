import logging
from typing import Optional

import time

import requests
from requests import Timeout

from domain.commodity import COMMODITY_SYMBOLS, CommodityType, WeightUnit
from domain.dezimal import Dezimal
from domain.exchange_rate import CommodityExchangeRate


class RMintApiPriceClient:
    BASE_URL = "https://www.royalmint.com/mvcApi/MetalPrice/GetChartData"
    TIMEOUT = 3

    SUPPORTED_COMMODITIES = {
        CommodityType.PLATINUM,
        CommodityType.GOLD,
        CommodityType.SILVER,
    }

    def __init__(self):
        self._log = logging.getLogger(__name__)

    def get_price(self, commodity: CommodityType) -> Optional[CommodityExchangeRate]:
        if commodity not in self.SUPPORTED_COMMODITIES:
            raise ValueError(f"Unsupported commodity type: {commodity}")

        return self._fetch_price(COMMODITY_SYMBOLS.get(commodity).lower())

    def _fetch_price(self, symbol: str) -> Optional[CommodityExchangeRate]:
        params = {
            "period": "Live",
            "currency": "eur",
            "commodity": symbol,
            "noCache": str(int(time.time() * 1000)),
        }

        try:
            data = self._fetch(self.BASE_URL, params)
        except Timeout as e:
            self._log.error(f"Timeout fetching price for {symbol}: {e}")
            return None

        if not data.get("success"):
            raise ValueError("API request was not successful")

        chart_data = data.get("chartData", [])
        if not chart_data:
            raise ValueError("No chart data available")

        latest_data = chart_data[-1]
        price = latest_data["Value"]

        return CommodityExchangeRate(
            unit=WeightUnit.TROY_OUNCE,
            currency="EUR",
            price=Dezimal(str(price)),
        )

    def _fetch(self, url: str, params: dict = None) -> dict:
        response = requests.get(url, params=params, timeout=self.TIMEOUT)
        if response.ok:
            return response.json()

        self._log.error("Error Response Body:" + response.text)
        response.raise_for_status()
        return {}
