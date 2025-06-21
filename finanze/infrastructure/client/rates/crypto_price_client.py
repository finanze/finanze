import logging

import requests
from application.ports.crypto_price_provider import CryptoPriceProvider
from cachetools import TTLCache, cached
from domain.dezimal import Dezimal


class CryptoPriceClient(CryptoPriceProvider):
    PRICE_CACHE_TTL = 10 * 60

    BASE_URL = "https://api.price2sheet.com/raw"

    SYMBOL_MAPPINGS = {
        "trx": "tron",
    }

    def __init__(self):
        self._log = logging.getLogger(__name__)

    def get_price(self, crypto_symbol: str, fiat_iso: str) -> Dezimal:
        return self._fetch_price(crypto_symbol.lower(), fiat_iso.lower())

    @cached(cache=TTLCache(maxsize=50, ttl=PRICE_CACHE_TTL))
    def _fetch_price(self, crypto_symbol: str, fiat_iso: str) -> Dezimal:
        url = f"{self.BASE_URL}/{self.SYMBOL_MAPPINGS.get(crypto_symbol, crypto_symbol)}/{fiat_iso}"
        raw = self._fetch(url)
        return Dezimal(raw)

    def _fetch(self, url: str) -> str:
        response = requests.get(url)
        if response.ok:
            return response.text

        self._log.error("Error Response Body:" + response.text)
        response.raise_for_status()
        return ""
