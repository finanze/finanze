import codecs
import logging
from datetime import date, datetime
from typing import Optional

from aiocache import cached, Cache
from domain.dezimal import Dezimal
from domain.instrument import (
    InstrumentDataRequest,
    InstrumentInfo,
    InstrumentOverview,
    InstrumentType,
)
from domain.instrument_history import InstrumentPricePoint
from infrastructure.client.http.http_session import get_http_session


class FinectClient:
    BASE_URL = "https://api.finect.com/v4"
    API_KEY = "BtpdnaHkD4F6L5IIiajyWnlHhkrt8Nu5"

    def __init__(self):
        self._session = get_http_session()
        self._session.headers.update(
            {
                "key": codecs.decode(self.API_KEY, "rot_13"),
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:144.0) Gecko/20100101 Firefox/144.0",
                "Accept": "application/json",
            }
        )
        self._log = logging.getLogger(__name__)

    async def search(self, request: InstrumentDataRequest) -> list[InstrumentOverview]:
        query = self._build_query(request)
        if not query:
            return []

        raw_items = await self._search_raw(query)
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

    @cached(cache=Cache.MEMORY, ttl=86400)
    async def _search_raw(self, query: str) -> list[dict]:
        if not query:
            return []

        params = {"q": query}
        response = await self._session.get(
            f"{self.BASE_URL}/search", params=params, timeout=10
        )
        if response.ok:
            data = await response.json()
            if isinstance(data, dict):
                items = data.get("data")
                if isinstance(items, list):
                    return items
                return []
            return []

        body = await response.text()
        self._log.error(
            "Finect Client error status=%s body=%s",
            response.status,
            body,
        )
        response.raise_for_status()
        return []

    async def get_history(
        self,
        request: InstrumentDataRequest,
        from_date: date,
        to_date: date,
        preferred_symbol: Optional[str] = None,
    ) -> tuple[list[InstrumentPricePoint], Optional[str], Optional[str]]:
        if preferred_symbol:
            product_id = preferred_symbol
            product_path = (
                "funds" if request.type == InstrumentType.MUTUAL_FUND else "etfs"
            )
        else:
            product_id, product_path = await self._resolve_product(request)
            if not product_id or not product_path:
                return [], None, None

        raw_points = await self._get_timeseries(product_path, product_id, from_date)
        points = self._parse_timeseries(raw_points, request, from_date, to_date)
        if not points:
            return [], None, None
        return points, product_id, "finect"

    async def _resolve_product(
        self, request: InstrumentDataRequest
    ) -> tuple[Optional[str], Optional[str]]:
        query = self._build_query(request)
        if not query:
            return None, None

        raw_items = await self._search_raw(query)
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            inferred_type = self._infer_type(item.get("type"))
            if not inferred_type:
                continue
            if request.type and inferred_type != request.type:
                continue
            entity = item.get("entity") if isinstance(item.get("entity"), dict) else {}
            isin = entity.get("isin") or None
            if request.isin and isin and isin.upper() != request.isin.upper():
                continue
            product_id = item.get("id") or entity.get("id")
            if not product_id:
                continue
            product_path = (
                "funds" if inferred_type == InstrumentType.MUTUAL_FUND else "etfs"
            )
            return product_id, product_path
        return None, None

    @cached(cache=Cache.MEMORY, ttl=86400)
    async def _get_timeseries(
        self, product_path: str, product_id: str, from_date: date
    ) -> list[dict]:
        response = await self._session.get(
            f"{self.BASE_URL}/products/collectives/{product_path}/{product_id}/timeseries",
            params={"start": from_date.isoformat()},
            timeout=30,
        )
        if not response.ok:
            body = await response.text()
            self._log.error(
                "Finect timeseries error status=%s body=%s",
                response.status,
                body,
            )
            if response.status == 404:
                return []
            response.raise_for_status()
            return []

        data = await response.json()
        if isinstance(data, dict):
            items = data.get("data")
            if isinstance(items, list):
                return items
        return []

    def _parse_timeseries(
        self,
        raw_points: list[dict],
        request: InstrumentDataRequest,
        from_date: date,
        to_date: date,
    ) -> list[InstrumentPricePoint]:
        points: list[InstrumentPricePoint] = []
        for item in raw_points:
            if not isinstance(item, dict):
                continue
            raw_dt = item.get("datetime")
            price_val = item.get("price")
            if not raw_dt or price_val is None:
                continue
            try:
                point_date = datetime.fromisoformat(
                    str(raw_dt).replace("Z", "+00:00")
                ).date()
                price = Dezimal(str(price_val))
            except Exception:
                self._log.exception(
                    "Failed to parse Finect timeseries point datetime=%s price=%s",
                    raw_dt,
                    price_val,
                )
                continue
            if point_date < from_date or point_date > to_date:
                continue
            points.append(
                InstrumentPricePoint(
                    date=point_date,
                    price=price,
                    currency=request.currency or "EUR",
                )
            )
        points.sort(key=lambda p: p.date)
        return points

    @cached(cache=Cache.MEMORY, ttl=43200)
    async def get_instrument_info(
        self, query: str, instrument_type: InstrumentType
    ) -> Optional[InstrumentInfo]:
        isin = query.strip()
        params = {"expand": "documents,breakdown,stats/performance"}
        product_type = (
            "funds" if instrument_type == InstrumentType.MUTUAL_FUND else "etfs"
        )
        response = await self._session.get(
            f"{self.BASE_URL}/products/collectives/{product_type}/{isin}",
            params=params,
            timeout=10,
        )
        if not response.ok:
            body = await response.text()
            self._log.error(
                "Finect get_instrument_info error status=%s body=%s",
                response.status,
                body,
            )
            if response.status == 404:
                return None
            response.raise_for_status()

        data = await response.json()
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
