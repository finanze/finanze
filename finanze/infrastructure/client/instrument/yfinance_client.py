import logging
from typing import Optional

import yfinance as yf
from aiocache import cached

from domain.dezimal import Dezimal
from domain.exception.exceptions import InstrumentProviderUnavailable
from domain.instrument import (
    InstrumentDataRequest,
    InstrumentInfo,
    InstrumentOverview,
    InstrumentType,
)


_LIQUID_EXCHANGES = ("MC", "MI", "XD", "XC", "F", "DE", "AS", "VI", "L")
_STALE_EXCHANGES = ("MU", "HA", "HM", "DU", "SG", "OQX", "MX")


class YFinanceClient:
    def __init__(self):
        self._log = logging.getLogger(__name__)

    async def lookup(self, request: InstrumentDataRequest) -> list[InstrumentOverview]:
        query = request.isin or request.ticker or request.name
        if not query:
            return []

        result = yf.Lookup(query)
        df = None
        if request.type == InstrumentType.MUTUAL_FUND:
            df = result.get_mutualfund()

        elif request.type == InstrumentType.ETF:
            df = result.get_etf()

        elif request.type == InstrumentType.STOCK:
            df = result.get_stock()

        if df is None or df.empty:
            return []

        results: list[InstrumentOverview] = []
        for _, row in df.iterrows():
            name = row.get("shortName") or row.get("longName") or row.get("name")
            symbol = row.name
            currency = row.get("currency")
            market = row.get("exchange")
            price = row.get("regularMarketPrice")
            price = round(Dezimal(price), 2) if price is not None else None

            results.append(
                InstrumentOverview(
                    isin=None,
                    name=name,
                    currency=str(currency) if currency else None,
                    symbol=symbol,
                    market=market,
                    price=price,
                    type=request.type,
                )
            )

        return results

    @cached(ttl=86400)
    async def _resolve_symbol_candidates(
        self, query: str, instrument_type: InstrumentType
    ) -> list[str]:
        if not query:
            return []

        result = yf.Lookup(query)
        df = None
        if instrument_type == InstrumentType.MUTUAL_FUND:
            df = result.get_mutualfund()
        elif instrument_type == InstrumentType.ETF:
            df = result.get_etf()
        elif instrument_type == InstrumentType.STOCK:
            df = result.get_stock()

        if df is None or df.empty:
            return [query] if self._looks_like_ticker(query) else []
        symbols = list(df.index)
        return sorted(symbols, key=self._exchange_priority)

    @staticmethod
    def _looks_like_isin(query: str) -> bool:
        return (
            len(query) == 12
            and query[:2].isalpha()
            and query[:2].isupper()
            and query[2:].isalnum()
        )

    @staticmethod
    def _looks_like_ticker(query: str) -> bool:
        if not query or len(query) > 12 or YFinanceClient._looks_like_isin(query):
            return False
        return all(char.isalnum() or char in ".-^=" for char in query)

    @staticmethod
    def _exchange_priority(symbol: str) -> int:
        suffix = symbol.rsplit(".", 1)[-1].upper() if "." in symbol else ""
        if suffix in _LIQUID_EXCHANGES:
            return 0
        if suffix in _STALE_EXCHANGES:
            return 2
        return 1

    async def _resolve_symbol(
        self, query: str, instrument_type: InstrumentType
    ) -> Optional[str]:
        if not query:
            return None

        result = yf.Lookup(query)
        if instrument_type == InstrumentType.MUTUAL_FUND:
            df = result.get_mutualfund()
            if df is not None and not df.empty:
                return df.iloc[0].name

        elif instrument_type == InstrumentType.ETF:
            df = result.get_etf()
            if df is not None and not df.empty:
                return df.iloc[0].name

        elif instrument_type == InstrumentType.STOCK:
            df = result.get_stock()
            if df is not None and not df.empty:
                return df.iloc[0].name

        if self._looks_like_ticker(query):
            return query
        return None

    @cached(ttl=60)
    async def get_instrument_info(
        self, query: str, instrument_type: InstrumentType
    ) -> Optional[InstrumentInfo]:
        symbol = await self._resolve_symbol(query, instrument_type)
        if not symbol:
            return None

        try:
            ticker = yf.Ticker(symbol)
        except Exception:
            self._log.exception("invalid ticker %s", symbol)
            return None

        price = None
        currency = None
        quote_type = None

        fast_info = getattr(ticker, "fast_info", None)
        if fast_info:
            price = fast_info.get("last_price")
            currency = fast_info.get("currency")
            quote_type = fast_info.get("quote_type")

        info = getattr(ticker, "info", {}) or {}

        if not price:
            price = info.get("regularMarketPrice") or info.get("previousClose")
        currency = currency or info.get("currency")
        name = info.get("longName") or info.get("shortName") or symbol
        quote_type = quote_type or info.get("quoteType")

        if price is None or currency is None:
            return None

        resolved_type = instrument_type or self._map_quote_type(quote_type)

        return InstrumentInfo(
            name=name,
            currency=str(currency),
            type=resolved_type,
            price=Dezimal(price),
            symbol=symbol,
        )

    @staticmethod
    def _map_quote_type(quote_type: Optional[str]) -> Optional[InstrumentType]:
        if not quote_type:
            return None
        qt = quote_type.upper()
        if qt in ("MUTUALFUND", "FUND"):
            return InstrumentType.MUTUAL_FUND
        if qt == "ETF":
            return InstrumentType.ETF
        if qt == "EQUITY":
            return InstrumentType.STOCK
        return None

    async def get_history(
        self,
        request: InstrumentDataRequest,
        from_date,
        to_date,
        preferred_symbol: Optional[str] = None,
    ) -> tuple[list, Optional[str], Optional[str]]:
        query = request.isin or request.ticker or request.name
        if not query:
            return [], None, None
        candidates = await self._resolve_symbol_candidates(query, request.type)
        if preferred_symbol:
            candidates.insert(0, preferred_symbol)
        if request.name and request.name != query:
            name_candidates = await self._resolve_symbol_candidates(
                request.name, request.type
            )
            candidates.extend(
                candidate
                for candidate in name_candidates
                if candidate not in candidates
            )

        seen: set[str] = set()
        fallback: tuple[list, str] | None = None
        failed = False
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            try:
                points = self._fetch_history(candidate, from_date, to_date)
            except Exception:
                self._log.exception("_fetch_history failed for %s", candidate)
                failed = True
                continue
            if not points:
                continue
            currency = self._fetch_currency(candidate)
            if not currency:
                failed = True
                continue
            if request.currency and currency != request.currency:
                continue
            for point in points:
                point.currency = currency
            if self._is_liquid(points):
                return points, candidate, "yfinance"
            if fallback is None:
                fallback = (points, candidate)
        if fallback is not None:
            points, candidate = fallback
            return points, candidate, "yfinance"
        if failed:
            raise InstrumentProviderUnavailable(query)
        return [], None, None

    async def get_splits(
        self,
        request: InstrumentDataRequest,
        from_date,
        to_date,
        preferred_symbol: Optional[str] = None,
    ) -> Optional[list]:
        from domain.instrument_history import InstrumentSplit

        symbol = preferred_symbol
        if not symbol:
            query = request.isin or request.ticker or request.name
            if not query:
                return []
            candidates = await self._resolve_symbol_candidates(query, request.type)
            symbol = candidates[0] if candidates else None
        if not symbol:
            return []

        try:
            ticker = yf.Ticker(symbol)
            history = ticker.history(start=from_date, end=to_date, auto_adjust=False)
        except Exception:
            self._log.exception("get_splits failed for %s", symbol)
            return None
        if history is None or history.empty or "Stock Splits" not in history.columns:
            return []
        splits = history["Stock Splits"]
        return [
            InstrumentSplit(date=moment.date(), ratio=Dezimal(str(ratio)))
            for moment, ratio in splits.items()
            if ratio and ratio > 0
        ]

    @staticmethod
    def _is_liquid(points: list) -> bool:
        if len(points) < 5:
            return True
        distinct = len({point.price for point in points})
        return distinct / len(points) >= 0.5

    def _fetch_history(self, symbol: str, from_date, to_date) -> list:
        import math

        from domain.instrument_history import InstrumentPricePoint

        ticker = yf.Ticker(symbol)
        history = ticker.history(start=from_date, end=to_date, auto_adjust=False)
        if history is None or history.empty:
            return []

        points = []
        for moment, row in history.iterrows():
            close = row.get("Close")
            if close is None:
                continue
            try:
                if not math.isfinite(float(close)):
                    continue
            except (TypeError, ValueError):
                continue
            points.append(
                InstrumentPricePoint(
                    date=moment.date(),
                    price=Dezimal(str(close)),
                    currency="",
                )
            )
        return points

    @staticmethod
    def _fetch_currency(symbol: str) -> Optional[str]:
        try:
            ticker = yf.Ticker(symbol)
        except Exception:
            return None
        fast_info = getattr(ticker, "fast_info", None)
        currency = fast_info.get("currency") if fast_info else None
        if currency:
            return str(currency)
        try:
            info = getattr(ticker, "info", {}) or {}
        except Exception:
            return None
        currency = info.get("currency")
        return str(currency) if currency else None
