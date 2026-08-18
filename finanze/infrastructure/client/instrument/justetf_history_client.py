import logging
from datetime import date
from typing import Optional

from aiocache import Cache, cached
from domain.dezimal import Dezimal
from domain.instrument import InstrumentDataRequest, InstrumentType
from domain.instrument_history import InstrumentPricePoint
from infrastructure.client.http.http_session import get_http_session


class JustEtfHistoryClient:
    """Standalone from the `jetf_client` package so mobile never pulls its bs4/pandas deps."""

    BASE_URL = "https://www.justetf.com/api/etfs/{isin}/performance-chart"
    SOURCE = "justetf"
    USER_AGENT = "My User Agent 1.0"

    def __init__(self):
        self._session = get_http_session()
        self._log = logging.getLogger(__name__)

    async def get_history(
        self,
        request: InstrumentDataRequest,
        from_date: date,
        to_date: date,
        preferred_symbol: Optional[str] = None,
    ) -> tuple[list[InstrumentPricePoint], Optional[str], Optional[str]]:
        if request.type != InstrumentType.ETF:
            return [], None, None

        isin = preferred_symbol or request.isin
        if not isin or not self._looks_like_isin(isin):
            return [], None, None

        currency = request.currency or "EUR"
        raw_series = await self._get_chart(isin, currency, from_date, to_date)
        points = self._parse_series(raw_series, currency, from_date, to_date)
        if not points:
            return [], None, None
        return points, isin, self.SOURCE

    @cached(cache=Cache.MEMORY, ttl=86400)
    async def _get_chart(
        self, isin: str, currency: str, from_date: date, to_date: date
    ) -> list[dict]:
        params = {
            "locale": "en",
            "currency": currency,
            "valuesType": "MARKET_VALUE",
            "reduceData": "false",
            "includeDividends": "false",
            "features": "DIVIDENDS",
            "dateFrom": from_date.isoformat(),
            "dateTo": to_date.isoformat(),
        }
        response = await self._session.get(
            self.BASE_URL.format(isin=isin),
            params=params,
            headers={"User-Agent": self.USER_AGENT},
            timeout=30,
        )
        if not response.ok:
            if response.status != 404:
                body = await response.text()
                self._log.error(
                    "JustETF chart error isin=%s status=%s body=%s",
                    isin,
                    response.status,
                    body[:500],
                )
            return []

        data = await response.json()
        if not isinstance(data, dict):
            return []
        series = data.get("series")
        return series if isinstance(series, list) else []

    def _parse_series(
        self,
        raw_series: list[dict],
        currency: str,
        from_date: date,
        to_date: date,
    ) -> list[InstrumentPricePoint]:
        points: list[InstrumentPricePoint] = []
        for item in raw_series:
            if not isinstance(item, dict):
                continue
            raw_date = item.get("date")
            value = item.get("value")
            raw_value = value.get("raw") if isinstance(value, dict) else None
            if not raw_date or raw_value is None:
                continue
            try:
                point_date = date.fromisoformat(str(raw_date))
                price = Dezimal(str(raw_value))
            except Exception:
                self._log.exception(
                    "Failed to parse JustETF point date=%s value=%s",
                    raw_date,
                    raw_value,
                )
                continue
            if point_date < from_date or point_date > to_date or not price:
                continue
            points.append(
                InstrumentPricePoint(date=point_date, price=price, currency=currency)
            )
        points.sort(key=lambda point: point.date)
        return points

    @staticmethod
    def _looks_like_isin(query: str) -> bool:
        return (
            len(query) == 12
            and query[:2].isalpha()
            and query[:2].isupper()
            and query[2:].isalnum()
        )
