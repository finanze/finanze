import abc
from datetime import date
from typing import Optional

from domain.instrument_history import InstrumentPricePoint, InstrumentSplit
from domain.instrument import InstrumentDataRequest


class InstrumentHistoryProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_history(
        self,
        request: InstrumentDataRequest,
        from_date: date,
        to_date: date,
        preferred_symbol: Optional[str] = None,
        preferred_source: Optional[str] = None,
    ) -> tuple[list[InstrumentPricePoint], Optional[str], Optional[str]]:
        """Return (points, symbol, source). symbol/source identify the winning
        provider so callers can persist and reuse them."""
        raise NotImplementedError

    async def get_splits(
        self,
        request: InstrumentDataRequest,
        from_date: date,
        to_date: date,
        preferred_symbol: Optional[str] = None,
        preferred_source: Optional[str] = None,
    ) -> Optional[list[InstrumentSplit]]:
        return []
