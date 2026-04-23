from typing import Optional

from aiocache import Cache, cached

from domain.dezimal import Dezimal
from domain.instrument import (
    InstrumentInfo,
    InstrumentType,
    InstrumentDataRequest,
    InstrumentOverview,
)

from .etf_profile import get_etf_overview


class JustEtfClient:
    async def search(self, request: InstrumentDataRequest) -> list[InstrumentOverview]:
        pass

    @cached(cache=Cache.MEMORY, ttl=43200)
    async def get_instrument_info(
        self, query: str, instrument_type: InstrumentType
    ) -> Optional[InstrumentInfo]:
        if instrument_type != InstrumentType.ETF:
            return None

        isin = query.strip()
        if not isin:
            return None

        overview = await get_etf_overview(
            isin=isin, include_gettex=True, expand_allocations=False
        )

        name = overview.get("name")
        currency = overview.get("fund_currency")

        price_val = None
        quote = overview.get("gettex")
        if quote is not None:
            price_val = getattr(quote, "mid", None) or getattr(quote, "last", None)
            if currency is None:
                currency = getattr(quote, "currency", None)

        if name is None or currency is None or price_val is None:
            return None

        try:
            price = Dezimal(str(price_val))
        except Exception:
            return None

        return InstrumentInfo(
            name=name,
            currency=currency,
            type=instrument_type,
            price=price,
            symbol=None,
        )
