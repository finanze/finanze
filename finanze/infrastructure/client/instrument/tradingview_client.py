import logging
from typing import Optional

from aiocache import cached, Cache
from domain.instrument import (
    InstrumentDataRequest,
    InstrumentOverview,
    InstrumentType,
)
from infrastructure.client.http.http_session import get_http_session


class TradingViewClient:
    SEARCH_URL = "https://symbol-search.tradingview.com/symbol_search/v3/"

    def __init__(self):
        self._session = get_http_session()
        self._session.headers.update(
            {
                "Origin": "https://es.tradingview.com",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:144.0) Gecko/20100101 Firefox/144.0",
                "Accept": "application/json",
            }
        )
        self._log = logging.getLogger(__name__)

    async def search(self, request: InstrumentDataRequest) -> list[InstrumentOverview]:
        if request.type != InstrumentType.STOCK:
            return []

        query = self._build_query(request)
        if not query:
            return []

        results: list[InstrumentOverview] = []
        for item in await self._search_raw(query):
            overview = self._process_raw_item(item, request)
            if overview:
                results.append(overview)
        return results

    @staticmethod
    def _build_query(request: InstrumentDataRequest) -> Optional[str]:
        return request.isin or request.ticker or request.name

    @staticmethod
    def _process_raw_item(
        item: dict, request: InstrumentDataRequest
    ) -> Optional[InstrumentOverview]:
        if not isinstance(item, dict):
            return None

        if item.get("type") != "stock":
            return None

        isin = item.get("isin") or None
        symbol = item.get("symbol") or None
        name = item.get("description") or None
        market = item.get("exchange") or None
        currency = item.get("currency_code") or None

        if not name:
            return None

        return InstrumentOverview(
            isin=isin,
            name=name,
            currency=currency,
            symbol=symbol,
            market=market,
            type=InstrumentType.STOCK,
        )

    @cached(cache=Cache.MEMORY, ttl=86400)
    async def _search_raw(self, query: str) -> list[dict]:
        if not query:
            return []
        params = {"text": query, "domain": "production", "search_type": "stocks"}
        try:
            response = await self._session.get(
                self.SEARCH_URL, params=params, timeout=10
            )
            if response.ok:
                data = await response.json()
                if isinstance(data, dict):
                    symbols = data.get("symbols")
                    if isinstance(symbols, list):
                        return symbols
                    return []
                return []
            body = await response.text()
            self._log.error(
                "TradingView search error status=%s body=%s",
                response.status,
                body,
            )
            response.raise_for_status()
        except Exception as e:
            self._log.exception("TradingView search request failed: %s", e)
        return []
