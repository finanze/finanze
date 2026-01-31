import logging

from domain.dezimal import Dezimal
from infrastructure.client.http.http_session import get_http_session


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
        self._session = get_http_session()

    def supports_symbol(self, symbol: str) -> bool:
        return symbol.upper() in self.SYMBOLS

    async def get_price(
        self, symbol: str, fiat_iso: str, request_timeout: int | None = None
    ) -> Dezimal:
        effective_timeout = request_timeout or self._timeout
        crypto_symbol = self.SYMBOL_OVERRIDES.get(symbol.upper(), symbol).lower()
        fiat = fiat_iso.lower()
        url = f"{self.BASE_URL}/{crypto_symbol}/{fiat}"
        raw = await self._fetch(url, effective_timeout)
        return Dezimal(raw)

    async def _fetch(self, url: str, request_timeout: int) -> str:
        response = await self._session.get(url, timeout=request_timeout)
        if response.ok:
            return await response.text()
        body = await response.text()
        self._log.error("Error Response Body:" + body)
        response.raise_for_status()
        return ""
