import logging
from typing import Optional

from aiocache import cached, Cache

from domain.dezimal import Dezimal
from domain.instrument import (
    InstrumentDataRequest,
    InstrumentInfo,
    InstrumentOverview,
    InstrumentType,
)
from infrastructure.client.http.http_session import get_http_session


class ExtraEtfClient:
    BASE_URL = "https://extraetf.com/"

    def __init__(self):
        self._session = get_http_session()
        self._session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:144.0) Gecko/20100101 Firefox/144.0",
                "Accept": "application/json",
            }
        )
        self._log = logging.getLogger(__name__)

    async def search(self, request: InstrumentDataRequest) -> list[InstrumentOverview]:
        if request.type not in (InstrumentType.ETF,):
            return []

        query = self._build_query(request)
        if not query:
            return []

        raw_docs = await self._search(query=query, limit=50, offset=0)
        if not raw_docs:
            return []

        results: list[InstrumentOverview] = []
        seen_isin: set[str] = set()
        for doc in raw_docs:
            overview = self._map_doc(doc, seen_isin)
            if overview:
                results.append(overview)

        return results

    @staticmethod
    def _build_query(request: InstrumentDataRequest) -> Optional[str]:
        return request.isin or request.ticker or request.name

    @staticmethod
    def _map_doc(doc: object, seen_isin: set[str]) -> Optional[InstrumentOverview]:
        if not isinstance(doc, dict):
            return None

        isin = _safe_str(doc.get("isin"))
        if not isin or isin in seen_isin:
            return None
        seen_isin.add(isin)

        fondname = _safe_str(doc.get("fondname"))
        name_field = _safe_str(doc.get("name"))
        name = fondname or name_field or isin

        currency = _safe_str(doc.get("currency")) or None
        # nav = doc.get("nav") # Prices don't seem to be reliable
        # price: Optional[Dezimal] = None
        # if nav is not None:
        #     try:
        #         price = Dezimal(str(nav))
        #     except Exception:
        #         self._log.debug(
        #             "Failed to parse nav as Dezimal for isin=%s nav=%r", isin, nav
        #         )

        return InstrumentOverview(
            isin=isin,
            name=name,
            currency=currency,
            symbol=None,
            market=None,
            type=InstrumentType.ETF,
            price=None,
        )

    @cached(cache=Cache.MEMORY, ttl=43200)
    async def get_instrument_info(
        self, query: str, instrument_type: InstrumentType
    ) -> Optional[InstrumentInfo]:
        if instrument_type not in (InstrumentType.ETF,):
            return None

        isin = query.strip()
        params = {"isin": isin, "extraetf_locale": "es"}
        response = await self._session.get(
            f"{self.BASE_URL}api-v2/detail/",
            params=params,
            timeout=6,
        )
        if not response.ok:
            body = await response.text()
            self._log.error(
                "ExtraETF get_instrument_info error status=%s body=%s",
                response.status,
                body,
            )
            if response.status == 404:
                return None
            response.raise_for_status()

        data = await response.json()
        if not isinstance(data, dict):
            return None

        results = data.get("results")
        if not isinstance(results, list) or not results:
            return None

        item = results[0]
        if not isinstance(item, dict):
            return None

        name = item.get("fondname")
        currency = item.get("currency")

        price_val = None
        returns = item.get("returns")
        if isinstance(returns, dict) and currency is not None:
            for return_data in returns.values():
                if not isinstance(return_data, dict):
                    continue

                price_currency = return_data.get("price_currency")
                if price_currency != currency:
                    continue

                close_price = return_data.get("close_price")
                if close_price is not None:
                    price_val = close_price
                    break

        if price_val is None:
            last_quote = item.get("last_quote")
            if isinstance(last_quote, dict):
                price_val = last_quote.get("m")
                currency = last_quote.get("c")

        if name is None or currency is None or price_val is None:
            return None

        try:
            price = Dezimal(str(price_val))
        except Exception:
            self._log.exception(
                "Failed to parse price for isin=%s price=%s", isin, price_val
            )
            return None

        return InstrumentInfo(
            name=name,
            currency=currency,
            type=instrument_type,
            price=price,
            symbol=None,
        )

    @cached(cache=Cache.MEMORY, ttl=3600)
    async def _search(self, query: str, limit: int = 50, offset: int = 0) -> list[dict]:
        if not query:
            return []
        params = {
            "limit": str(limit),
            "offset": str(offset),
            "leverage": "0",
            "product_type": "etf,etc",
            "query": query,
            "enable_promotions": "false",
        }
        response = await self._session.get(
            self.BASE_URL + "/api-v3/search/full/", params=params, timeout=15
        )

        if not response.ok:
            body = await response.text()
            self._log.error(
                "ExtraETF API error status=%s body=%s query=%s",
                response.status,
                body,
                query,
            )
            response.raise_for_status()

        data = await response.json()
        if not isinstance(data, dict):
            return []

        docs = data.get("docs")
        if isinstance(docs, list):
            return docs

        return []


def _safe_str(value: object) -> Optional[str]:
    if isinstance(value, str):
        v = value.strip()
        return v if v else None
    return None
