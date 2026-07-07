import logging
from typing import Optional

from domain.dezimal import Dezimal
from infrastructure.client.http.http_session import get_http_session


class DIAClient:
    BASE_URL = "https://api.diadata.org/v1"
    DEFAULT_TIMEOUT = 6

    SYMBOLS = {
        "BTC",
        "ETH",
        "LTC",
        "TRX",
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
        "POL",
        "MATIC",
        "LINK",
        "ATOM",
        "UNI",
        "XLM",
        "FTM",
    }

    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._timeout = self.DEFAULT_TIMEOUT
        self._session = get_http_session()

    def supports_symbol(self, symbol: str) -> bool:
        return symbol.upper() in self.SYMBOLS

    async def get_quotation(
        self, symbol: str, request_timeout: int | None = None
    ) -> dict:
        effective_timeout = request_timeout or self._timeout
        url = f"{self.BASE_URL}/quotation/{symbol.upper()}"
        return await self._fetch(url, effective_timeout)

    async def get_asset_quotation(
        self, blockchain: str, address: str, request_timeout: int | None = None
    ) -> dict:
        effective_timeout = request_timeout or self._timeout
        url = f"{self.BASE_URL}/assetQuotation/{blockchain}/{address}"
        return await self._fetch(url, effective_timeout)

    async def get_quoted_assets(
        self, blockchain: Optional[str] = None, request_timeout: int | None = None
    ) -> list[dict]:
        effective_timeout = request_timeout or self._timeout
        url = f"{self.BASE_URL}/quotedAssets"
        params = {"blockchain": blockchain} if blockchain else None
        return await self._fetch(url, effective_timeout, params=params)

    async def get_price(
        self, symbol: str, request_timeout: int | None = None
    ) -> Dezimal:
        data = await self.get_quotation(symbol, request_timeout)
        price = data.get("Price")
        if price is None:
            raise ValueError(f"DIA quotation for {symbol} missing Price field")
        return Dezimal(price)

    async def _fetch(self, url: str, request_timeout: int, params: dict = None):
        response = await self._session.get(url, params=params, timeout=request_timeout)
        if response.ok:
            return await response.json()
        body = await response.text()
        self._log.error("Error Response Body:" + body)
        response.raise_for_status()
        return {}
