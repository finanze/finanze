import logging
from typing import Optional

import yfinance as yf
from cachetools import TTLCache, cached
from domain.dezimal import Dezimal
from domain.instrument import (
    InstrumentDataRequest,
    InstrumentInfo,
    InstrumentOverview,
    InstrumentType,
)


class YFinanceClient:
    def __init__(self):
        self._log = logging.getLogger(__name__)

    def lookup(self, request: InstrumentDataRequest) -> list[InstrumentOverview]:
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

    @cached(cache=TTLCache(maxsize=100, ttl=86400))
    def _resolve_symbol(
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

        return query

    @cached(cache=TTLCache(maxsize=100, ttl=60))
    def get_instrument_info(
        self, query: str, instrument_type: InstrumentType
    ) -> Optional[InstrumentInfo]:
        symbol = self._resolve_symbol(query, instrument_type)
        if not symbol:
            return None

        ticker = yf.Ticker(symbol)

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
