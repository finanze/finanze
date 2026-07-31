import logging
import re
from typing import Optional

from aiocache import cached, Cache

from domain.dezimal import Dezimal
from domain.instrument import (
    InstrumentDataRequest,
    InstrumentOverview,
    InstrumentType,
)
from infrastructure.client.http.http_session import get_http_session


_ISIN_REGEX = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]")


class BoursierClient:
    BASE_URL = "https://www.boursier.com/typeahead/search-instrument"

    def __init__(self):
        self._session = get_http_session()
        self._session.headers.update(
            {
                "Origin": "https://www.boursier.com",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:144.0) Gecko/20100101 Firefox/144.0",
                "Accept": "application/json",
            }
        )
        self._log = logging.getLogger(__name__)

    async def search(self, request: InstrumentDataRequest) -> list[InstrumentOverview]:
        if request.type != InstrumentType.MUTUAL_FUND:
            return []

        query = request.isin or request.ticker or request.name
        if not query:
            return []

        raw_items = await self._search_raw(query)
        results: list[InstrumentOverview] = []
        for item in raw_items:
            overview = self._process_item(item)
            if overview:
                results.append(overview)
        return results

    def _process_item(self, item: object) -> Optional[InstrumentOverview]:
        if not isinstance(item, dict) or item.get("nature") != "OPCVM":
            return None

        name = _safe_str(item.get("name"))
        if not name:
            return None

        section = item.get("section")
        url = item.get("url")
        isin = _extract_isin(section) or _extract_isin(url)
        symbol = _safe_str(item.get("code"))

        quote = item.get("quote") if isinstance(item.get("quote"), dict) else {}
        price_value = quote.get("price")
        price = _parse_price(price_value)
        currency = "EUR" if _has_euro_symbol(price_value) else None

        return InstrumentOverview(
            isin=isin,
            name=name,
            currency=currency,
            symbol=symbol,
            market=None,
            type=InstrumentType.MUTUAL_FUND,
            price=price,
        )

    @cached(cache=Cache.MEMORY, ttl=86400)
    async def _search_raw(self, query: str) -> list[dict]:
        response = await self._session.post(
            self.BASE_URL,
            data={"q": query},
            timeout=10,
        )
        if response.ok:
            data = await response.json()
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
            return []

        body = await response.text()
        self._log.error(
            "Boursier Client error status=%s body=%s",
            response.status,
            body,
        )
        response.raise_for_status()
        return []


def _safe_str(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _extract_isin(value: object) -> Optional[str]:
    text = _safe_str(value)
    if not text:
        return None
    match = _ISIN_REGEX.search(text.upper())
    return match.group(0) if match else None


def _has_euro_symbol(value: object) -> bool:
    return isinstance(value, str) and "€" in value


def _parse_price(value: object) -> Optional[Dezimal]:
    if not isinstance(value, str):
        return None

    normalized = value.strip().replace("\xa0", "").replace(" ", "")
    normalized = normalized.replace("€", "")
    if not normalized:
        return None

    if "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")

    try:
        return Dezimal(normalized)
    except ValueError:
        return None
