import logging

import requests
from application.ports.crypto_price_provider import CryptoPriceProvider
from cachetools import TTLCache, cached
from domain.dezimal import Dezimal
from domain.global_position import CRYPTO_SYMBOLS, CryptoAsset, CryptoCurrency


class CryptoPriceClient(CryptoPriceProvider):
    PRICE_CACHE_TTL = 10 * 60
    TIMEOUT = 7

    BASE_URL = "https://api.price2sheet.com/raw"

    SYMBOL_OVERRIDES = {
        CryptoCurrency.TRON: "tron",
    }

    def __init__(self):
        self._log = logging.getLogger(__name__)

    @cached(cache=TTLCache(maxsize=50, ttl=PRICE_CACHE_TTL))
    def get_price(self, crypto: CryptoAsset, fiat_iso: str, **kwargs) -> Dezimal:
        timeout = kwargs.get("timeout", self.TIMEOUT)
        return self._fetch_price(
            self.SYMBOL_OVERRIDES.get(crypto, CRYPTO_SYMBOLS.get(crypto)).lower(),
            fiat_iso.lower(),
            timeout,
        )

    def _fetch_price(self, crypto_symbol: str, fiat_iso: str, timeout: int) -> Dezimal:
        url = f"{self.BASE_URL}/{crypto_symbol}/{fiat_iso}"
        raw = self._fetch(url, timeout)
        return Dezimal(raw)

    def _fetch(self, url: str, timeout: int) -> str:
        response = requests.get(url, timeout=timeout)
        if response.ok:
            return response.text

        self._log.error("Error Response Body:" + response.text)
        response.raise_for_status()
        return ""
