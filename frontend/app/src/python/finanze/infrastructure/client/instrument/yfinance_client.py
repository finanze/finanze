import json
import logging
from typing import Optional

import js
from aiocache import cached

from domain.dezimal import Dezimal
from domain.exception.exceptions import InstrumentProviderUnavailable
from domain.instrument import (
    InstrumentDataRequest,
    InstrumentInfo,
    InstrumentOverview,
    InstrumentType,
)
from domain.instrument_history import InstrumentPricePoint, InstrumentSplit

_LIQUID_EXCHANGES = ("MC", "MI", "XD", "XC", "F", "DE", "AS", "VI", "L")
_STALE_EXCHANGES = ("MU", "HA", "HM", "DU", "SG", "OQX", "MX")


class YFinanceClient:
    def __init__(self):
        self._log = logging.getLogger(__name__)

    async def lookup(self, request: InstrumentDataRequest) -> list[InstrumentOverview]:
        query = request.isin or request.ticker or request.name
        if not query:
            return []

        try:
            raw = await js.jsBridge.yahooFinance.lookup(query, request.type.value)
            items = json.loads(raw)
        except Exception:
            self._log.exception("yahooFinance bridge lookup failed")
            return []

        results: list[InstrumentOverview] = []
        for item in items:
            price = item.get("price")
            price = round(Dezimal(price), 2) if price is not None else None

            results.append(
                InstrumentOverview(
                    isin=None,
                    name=item.get("name"),
                    currency=item.get("currency"),
                    symbol=item.get("symbol"),
                    market=item.get("exchange"),
                    price=price,
                    type=self._parse_type(item.get("quoteType")) or request.type,
                )
            )

        return results

    @cached(ttl=60)
    async def get_instrument_info(
        self, query: str, instrument_type: InstrumentType
    ) -> Optional[InstrumentInfo]:
        if not query:
            return None

        try:
            raw = await js.jsBridge.yahooFinance.getInstrumentInfo(
                query, instrument_type.value
            )
            data = json.loads(raw)
        except Exception:
            self._log.exception("yahooFinance bridge getInstrumentInfo failed")
            return None

        if data is None:
            return None

        resolved_type = self._parse_type(data.get("type")) or instrument_type

        return InstrumentInfo(
            name=data["name"],
            currency=data["currency"],
            type=resolved_type,
            price=Dezimal(data["price"]),
            symbol=data.get("symbol"),
        )

    @staticmethod
    def _parse_type(value: Optional[str]) -> Optional[InstrumentType]:
        if not value:
            return None
        try:
            return InstrumentType(value)
        except ValueError:
            return None

    @staticmethod
    def _exchange_priority(symbol: str) -> int:
        suffix = symbol.rsplit(".", 1)[-1].upper() if "." in symbol else ""
        if suffix in _LIQUID_EXCHANGES:
            return 0
        if suffix in _STALE_EXCHANGES:
            return 2
        return 1

    @staticmethod
    def _is_liquid(points: list) -> bool:
        if len(points) < 5:
            return True
        distinct = len({point.price for point in points})
        return distinct / len(points) >= 0.5

    async def _resolve_candidates(
        self, query: str, instrument_type: InstrumentType
    ) -> list[str]:
        if not query:
            return []
        try:
            raw = await js.jsBridge.yahooFinance.lookup(query, instrument_type.value)
            items = json.loads(raw)
        except Exception:
            self._log.exception("yahooFinance bridge candidate lookup failed")
            return [query] if self._looks_like_ticker(query) else []
        symbols = [item["symbol"] for item in items if item.get("symbol")]
        if not symbols:
            return [query] if self._looks_like_ticker(query) else []
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

    async def _fetch_history(
        self, symbol: str, from_date, to_date
    ) -> tuple[list, Optional[str]]:
        raw = await js.jsBridge.yahooFinance.getHistory(
            symbol, from_date.isoformat(), to_date.isoformat()
        )
        data = json.loads(raw)
        currency = data.get("currency")
        if not currency:
            return [], None
        points = [
            InstrumentPricePoint(
                date=item["date"],
                price=Dezimal(str(item["price"])),
                currency=currency,
            )
            for item in data.get("points", [])
        ]
        return points, currency

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
        candidates = await self._resolve_candidates(query, request.type)
        if preferred_symbol:
            candidates.insert(0, preferred_symbol)
        if request.name and request.name != query:
            name_candidates = await self._resolve_candidates(request.name, request.type)
            candidates.extend(
                candidate
                for candidate in name_candidates
                if candidate not in candidates
            )

        seen: set[str] = set()
        fallback: Optional[tuple[list, str]] = None
        failed = False
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            try:
                points, currency = await self._fetch_history(
                    candidate, from_date, to_date
                )
            except Exception:
                self._log.exception("yahooFinance bridge getHistory failed")
                failed = True
                continue
            if not points:
                continue
            if request.currency and currency != request.currency:
                continue
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
        symbol = preferred_symbol
        if not symbol:
            query = request.isin or request.ticker or request.name
            if not query:
                return []
            candidates = await self._resolve_candidates(query, request.type)
            symbol = candidates[0] if candidates else None
        if not symbol:
            return []

        try:
            raw = await js.jsBridge.yahooFinance.getSplits(
                symbol, from_date.isoformat(), to_date.isoformat()
            )
            items = json.loads(raw)
            return [
                InstrumentSplit(date=item["date"], ratio=Dezimal(str(item["ratio"])))
                for item in items
                if item.get("ratio") and item["ratio"] > 0
            ]
        except Exception:
            self._log.exception("yahooFinance bridge getSplits failed")
            return None
