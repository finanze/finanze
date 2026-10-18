from dataclasses import field
from datetime import date

from domain.dezimal import Dezimal
from pydantic.dataclasses import dataclass

REAL_ESTATE_BUCKET = "REAL_ESTATE"
REAL_ESTATE_RESIDENCE_BUCKET = "REAL_ESTATE_RESIDENCE"


@dataclass
class NetworthSummaryQuery:
    base_currency: str


@dataclass
class NetworthSummary:
    currency: str
    date: date
    total: Dezimal
    breakdown: dict[str, Dezimal] = field(default_factory=dict)
