import logging
import time
from typing import Optional

import requests
from domain.commodity import COMMODITY_SYMBOLS, CommodityType, WeightUnit
from domain.dezimal import Dezimal
from domain.exchange_rate import CommodityExchangeRate
from requests import Timeout


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

    def get_price(
        self, commodity: CommodityType, timeout: int | None = None
    ) -> Optional[CommodityExchangeRate]:
        if commodity not in self.SUPPORTED_COMMODITIES:
            raise ValueError(f"Unsupported commodity type: {commodity}")

        return self._fetch_price(
            COMMODITY_SYMBOLS.get(commodity).lower(), timeout or self.TIMEOUT
        )

    def _fetch_price(
        self, symbol: str, timeout: int
    ) -> Optional[CommodityExchangeRate]:
        params = {
            "period": "Live",
            "currency": "eur",
            "commodity": symbol,
            "noCache": str(int(time.time() * 1000)),
        }

        try:
            data = self._fetch(self.BASE_URL, timeout, params)
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

    def _fetch(self, url: str, timeout: int, params: dict = None) -> dict:
        response = requests.get(url, params=params, timeout=timeout)
        if response.ok:
            return response.json()

        self._log.error("Error Response Body:" + response.text)
        response.raise_for_status()
        return {}
