import codecs
import logging
from typing import Optional

import requests
from cachetools import TTLCache, cached
from domain.dezimal import Dezimal
from domain.instrument import (
    InstrumentDataRequest,
    InstrumentInfo,
    InstrumentOverview,
    InstrumentType,
)


class FinectClient:
    BASE_URL = "https://api.finect.com/v4"
    API_KEY = "BtpdnaHkD4F6L5IIiajyWnlHhkrt8Nu5"

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(
            {
                "key": codecs.decode(self.API_KEY, "rot_13"),
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:144.0) Gecko/20100101 Firefox/144.0",
                "Accept": "application/json",
            }
        )
        self._log = logging.getLogger(__name__)

    def search(self, request: InstrumentDataRequest) -> list[InstrumentOverview]:
        query = self._build_query(request)
        if not query:
            return []

        raw_items = self._search_raw(query)
        results: list[InstrumentOverview] = []
        for item in raw_items:
            overview = self._process_item(item, request)
            if overview:
                results.append(overview)
        return results

    @staticmethod
    def _build_query(request: InstrumentDataRequest) -> Optional[str]:
        return request.isin or request.ticker or request.name

    @staticmethod
    def _infer_type(raw_type: Optional[str]) -> Optional[InstrumentType]:
        if raw_type == "etf":
            return InstrumentType.ETF
        if raw_type in ("fund", "plan"):
            return InstrumentType.MUTUAL_FUND
        return None

    def _process_item(
        self, item: dict, request: InstrumentDataRequest
    ) -> Optional[InstrumentOverview]:
        if not isinstance(item, dict):
            return None
        inferred_type = self._infer_type(item.get("type"))
        if not inferred_type:
            return None

        entity = item.get("entity") if isinstance(item.get("entity"), dict) else {}
        isin = entity.get("isin") or None
        title = item.get("title") or None
        fund_class_name = entity.get("fund_class_name") or None
        fund_name = entity.get("fund_name") or None

        if request.type and inferred_type != request.type:
            return None

        name = title or fund_class_name or fund_name
        if not name:
            return None

        return InstrumentOverview(
            isin=isin,
            name=name,
            currency=None,
            symbol=None,
            market=None,
            type=inferred_type,
        )

    @cached(cache=TTLCache(maxsize=200, ttl=86400))
    def _search_raw(self, query: str) -> list[dict]:
        if not query:
            return []

        params = {"q": query}
        response = self._session.get(
            f"{self.BASE_URL}/search", params=params, timeout=10
        )
        if response.ok:
            data = response.json()
            if isinstance(data, dict):
                items = data.get("data")
                if isinstance(items, list):
                    return items
                return []
            return []

        self._log.error(
            "Finect Client error status=%s body=%s",
            response.status_code,
            response.text,
        )
        response.raise_for_status()
        return []

    @cached(cache=TTLCache(maxsize=200, ttl=43200))
    def get_instrument_info(
        self, query: str, instrument_type: InstrumentType
    ) -> Optional[InstrumentInfo]:
        if not query:
            return None

        isin = query.strip()
        params = {"expand": "documents,breakdown,stats/performance"}
        product_type = (
            "funds" if instrument_type == InstrumentType.MUTUAL_FUND else "etfs"
        )
        response = self._session.get(
            f"{self.BASE_URL}/products/collectives/{product_type}/{isin}",
            params=params,
            timeout=10,
        )
        if not response.ok:
            self._log.error(
                "Finect get_instrument_info error status=%s body=%s",
                response.status_code,
                response.text,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()

        data = response.json()
        if not isinstance(data, dict):
            return None

        item = data.get("data")
        if not isinstance(item, dict):
            return None

        name = (item.get("class") or {}).get("name") or item.get("name")
        currency = (item.get("currency") or {}).get("code")

        last_quote = (
            item.get("lastQuote") if isinstance(item.get("lastQuote"), dict) else {}
        )
        price_val = last_quote.get("price")

        if name is None or currency is None or price_val is None:
            return None

        try:
            price = Dezimal(price_val)
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
