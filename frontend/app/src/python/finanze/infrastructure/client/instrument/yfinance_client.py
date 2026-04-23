import json
import logging
from typing import Optional

import js
from aiocache import cached

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
