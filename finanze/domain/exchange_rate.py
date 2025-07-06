from dataclasses import dataclass

from domain.commodity import WeightUnit
from domain.dezimal import Dezimal

ExchangeRates = dict[str, dict[str, Dezimal]]


@dataclass
class CommodityExchangeRate:
    unit: WeightUnit
    currency: str
    price: Dezimal
