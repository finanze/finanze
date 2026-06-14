from dataclasses import field
from datetime import date, datetime
from typing import Optional

from domain.commodity import CommodityType, WeightUnit
from domain.dezimal import Dezimal
from domain.global_position import ProductType
from pydantic.dataclasses import dataclass

REAL_ESTATE_BUCKET = "REAL_ESTATE"
REAL_ESTATE_RESIDENCE_BUCKET = "REAL_ESTATE_RESIDENCE"

# Commodity market values were not refreshed daily before this date, so stored
# valuations may be stale: days before the cutoff are revalued from historic
# metal prices, days from it onwards trust the stored (daily-updated) values.
COMMODITY_HISTORIC_CUTOFF = date(2026, 6, 12)


@dataclass
class NetworthTimelinePoint:
    date: date
    total: Dezimal
    breakdown: dict[str, Dezimal] = field(default_factory=dict)


@dataclass
class NetworthTimeline:
    currency: str
    points: list[NetworthTimelinePoint] = field(default_factory=list)


@dataclass
class NetworthTimelineQuery:
    base_currency: str = "EUR"
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    no_calculation: bool = False


@dataclass
class HoldingValuation:
    """Value of a single product holding within a position snapshot, in its native currency."""

    product_type: ProductType
    currency: Optional[str]
    amount: Dezimal
    loan_ref: Optional[str] = None
    commodity_type: Optional[CommodityType] = None
    weight: Optional[Dezimal] = None
    weight_unit: Optional[WeightUnit] = None


@dataclass
class PositionSnapshot:
    """A point-in-time valuation of one holder's position.

    A holder reports successive snapshots over time, and the latest snapshot on
    or before a day represents its value on that day. ``holder_deleted_at`` is
    the date the holder account was deleted (if any); from that day on the
    holder no longer contributes.

    For per-account sources (bank fetches), one snapshot is produced per
    account and the holder is that account. For sources whose every import
    fully re-declares the portfolio (manual entries, Sheets), a single
    ``redeclaring`` snapshot is produced per import: the holder is the source
    itself and the holdings are the whole portfolio declared by that import, so
    the latest import on or before a day fully replaces the previous one.
    """

    holder: str
    moment: datetime
    holdings: list[HoldingValuation] = field(default_factory=list)
    holder_deleted_at: Optional[date] = None
    redeclaring: bool = False


@dataclass
class MortgageValuation:
    """Outstanding principal of a property-linked mortgage at a point in time."""

    loan_ref: str
    moment: datetime
    outstanding: Dezimal
    currency: str
    origination: Optional[date] = None


@dataclass
class NetworthTimelineState:
    """Memoization state of the computed timeline cache.

    ``inputs_signature`` is a hash of the inputs that affect every stored value
    (target currency, excluded entities, property-linked mortgages). When it
    changes, the cache is stale and must be rebuilt from scratch.
    ``last_computed_date`` is the most recent day already memoized.
    """

    inputs_signature: Optional[str] = None
    last_computed_date: Optional[date] = None
