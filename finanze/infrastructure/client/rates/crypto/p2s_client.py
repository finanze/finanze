import logging

import requests
from domain.dezimal import Dezimal


class P2SClient:
    BASE_URL = "https://api.price2sheet.com/raw"
    DEFAULT_TIMEOUT = 7

    SYMBOLS = {
        "BTC",
        "ETH",
        "LTC",
        "TRON",
        "TRX",  # alias for TRON
        "BNB",
        "USDT",
        "USDC",
        "SOL",
        "ADA",
        "DOGE",
        "DOT",
        "XRP",
        "XMR",
        "AVAX",
        "MATIC",
        "LINK",
        "ATOM",
        "UNI",
        "XLM",
        "FTM",
    }
    SYMBOL_OVERRIDES = {"TRX": "tron"}

    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._timeout = self.DEFAULT_TIMEOUT

    def supports_symbol(self, symbol: str) -> bool:
        return symbol.upper() in self.SYMBOLS

    def get_price(
        self, symbol: str, fiat_iso: str, timeout: int | None = None
    ) -> Dezimal:
        effective_timeout = timeout or self._timeout
        crypto_symbol = self.SYMBOL_OVERRIDES.get(symbol.upper(), symbol).lower()
        fiat = fiat_iso.lower()
        url = f"{self.BASE_URL}/{crypto_symbol}/{fiat}"
        raw = self._fetch(url, effective_timeout)
        return Dezimal(raw)

    def _fetch(self, url: str, timeout: int) -> str:
        response = requests.get(url, timeout=timeout)
        if response.ok:
            return response.text
        self._log.error("Error Response Body:" + response.text)
        response.raise_for_status()
        return ""
