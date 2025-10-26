import logging
from typing import Optional

import requests
from cachetools import TTLCache, cached
from domain.instrument import InstrumentDataRequest, InstrumentOverview, InstrumentType


class ExtraEtfClient:
    BASE_URL = "https://extraetf.com/api-v3/search/full/"

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:144.0) Gecko/20100101 Firefox/144.0",
                "Accept": "application/json",
            }
        )
        self._log = logging.getLogger(__name__)

    def search(self, request: InstrumentDataRequest) -> list[InstrumentOverview]:
        if request.type not in (InstrumentType.ETF,):
            return []

        query = self._build_query(request)
        if not query:
            return []

        raw_docs = self._search(query=query, limit=50, offset=0)
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

    @cached(cache=TTLCache(maxsize=200, ttl=3600))
    def _search(self, query: str, limit: int = 50, offset: int = 0) -> list[dict]:
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
        response = self._session.get(self.BASE_URL, params=params, timeout=15)

        if not response.ok:
            self._log.error(
                "ExtraETF API error status=%s body=%s query=%s",
                response.status_code,
                response.text,
                query,
            )
            response.raise_for_status()

        data = response.json()
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
