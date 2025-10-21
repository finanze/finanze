import logging
import re
from typing import Optional

import requests
from cachetools import TTLCache, cached
from domain.instrument import InstrumentDataRequest, InstrumentOverview, InstrumentType

_ISIN_REGEX = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
_CURRENCY_REGEX = re.compile(r"^[A-Z]{3}$")


class FtClient:
    BASE_URL = "https://www.ft.com/search-api/suggestions"

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:144.0) Gecko/20100101 Firefox/144.0"
            }
        )
        self._log = logging.getLogger(__name__)

    def search(self, request: InstrumentDataRequest) -> list[InstrumentOverview]:
        query = request.isin or request.ticker or request.name
        if not query:
            return []

        equities = self._search_equities(query)
        instrument_type = request.type
        results: list[InstrumentOverview] = []
        for eq in equities:
            symbol_str = eq.get("symbol") if isinstance(eq, dict) else None
            name = eq.get("name") if isinstance(eq, dict) else None
            if not symbol_str or not name:
                continue

            parsed = self._parse_symbol(symbol_str)
            if not parsed:
                continue

            isin, currency, market, inferred_type, ticker = parsed

            if (
                instrument_type and instrument_type == InstrumentType.MUTUAL_FUND
            ) and inferred_type != InstrumentType.MUTUAL_FUND:
                continue
            if (
                instrument_type and instrument_type != InstrumentType.MUTUAL_FUND
            ) and inferred_type == InstrumentType.MUTUAL_FUND:
                continue

            results.append(
                InstrumentOverview(
                    isin=isin,
                    name=name,
                    currency=currency,
                    symbol=ticker,
                    market=market,
                    type=instrument_type or inferred_type,
                )
            )

        return results

    @cached(cache=TTLCache(maxsize=100, ttl=86400))
    def _search_equities(self, partial: str, count: int = 100) -> list[dict]:
        if not partial:
            return []

        params = {"partial": partial, "only": "equities", "count": str(count)}
        response = self._session.get(self.BASE_URL, params=params, timeout=10)
        if response.ok:
            data = response.json()
            if (
                isinstance(data, dict)
                and "equities" in data
                and isinstance(data["equities"], list)
            ):
                return data["equities"]

            return []

        self._log.error(
            "FT Client error status=%s body=%s", response.status_code, response.text
        )
        response.raise_for_status()

        return []

    @staticmethod
    @cached(cache=TTLCache(maxsize=100, ttl=86400))
    def _parse_symbol(
        symbol: str,
    ) -> Optional[
        tuple[
            Optional[str], Optional[str], Optional[str], InstrumentType, Optional[str]
        ]
    ]:
        """Parse FT symbol into (isin, currency, market, type, ticker).

        Returns:
        - isin: ISIN string for mutual funds (or None)
        - currency: ISO currency code if present (or None)
        - market: market/exchange identifier if present (or None)
        - type: inferred InstrumentType
        - ticker: the ticker component (or None for pure ISIN entries)

        Patterns handled:
        - ISIN:CURRENCY -> mutual fund with ISIN, currency (ticker=None)
        - ISIN -> mutual fund (ticker=None)
        - TICKER:MARKET -> stock (ticker=TICKER, market=MARKET)
        - TICKER:MARKET:CURRENCY -> ETF (ticker=TICKER, market=MARKET, currency=CURRENCY)
        - TICKER:MARKET:XXX where XXX is not an ISO currency -> treat last segment as market
          and return it as market (ticker=TICKER)
        """
        parts = symbol.split(":")
        # Two-part patterns
        if len(parts) == 2:
            left, right = parts
            # ISIN:CURRENCY -> mutual fund
            if _ISIN_REGEX.match(left) and _CURRENCY_REGEX.match(right):
                return left, right, None, InstrumentType.MUTUAL_FUND, None

            # Otherwise assume TICKER:MARKET -> stock
            return None, None, right if right else None, InstrumentType.STOCK, left

        # Three-part patterns: TICKER:MARKET:CURRENCY (or unusual variants)
        if len(parts) == 3:
            left, market, last = parts
            if _CURRENCY_REGEX.match(last):
                # Standard ETF pattern
                return None, last, market if market else None, InstrumentType.ETF, left

            inferred_market = last if last else (market if market else None)
            return None, None, inferred_market, InstrumentType.ETF, left

        # Symbol is just an ISIN
        if _ISIN_REGEX.match(symbol):
            return symbol, None, None, InstrumentType.MUTUAL_FUND, None

        return None
