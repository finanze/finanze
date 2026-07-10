from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from domain.commodity import WeightUnit
from domain.dezimal import Dezimal

ExchangeRates = dict[str, dict[str, Dezimal]]


@dataclass
class CommodityExchangeRate:
    unit: WeightUnit
    currency: str
    price: Dezimal


@dataclass(frozen=True)
class HistoricMetalRates:
    """A sparse daily series of metal prices per troy ounce.

    ``days`` is ascending and each currency series in ``prices`` is aligned to
    it. ``price_at`` resolves a missing day to the closest previous known day,
    so gaps (if any) are handled on lookup rather than expanded in memory.
    """

    unit: WeightUnit
    days: tuple[date, ...]
    prices: dict[str, tuple[Dezimal, ...]] = field(default_factory=dict)

    @property
    def currencies(self) -> tuple[str, ...]:
        return tuple(self.prices.keys())

    def price_at(self, day: date, currency: str) -> Optional[Dezimal]:
        series = self.prices.get(currency)
        if not series:
            return None
        index = bisect_right(self.days, day) - 1
        if index < 0:
            index = 0
        return series[index]
