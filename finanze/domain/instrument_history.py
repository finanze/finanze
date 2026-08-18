from datetime import date
from typing import Optional

from domain.dezimal import Dezimal
from pydantic.dataclasses import dataclass


@dataclass
class InstrumentPricePoint:
    date: date
    price: Dezimal
    currency: str


@dataclass
class InstrumentSplit:
    date: date
    ratio: Dezimal


@dataclass
class InstrumentHistoryQuery:
    instrument_key: str
    from_date: date
    to_date: date
    isin: Optional[str] = None
    ticker: Optional[str] = None
    name: Optional[str] = None
