from enum import Enum
from typing import Optional

from domain.dezimal import Dezimal
from pydantic.dataclasses import dataclass


class CommodityType(str, Enum):
    GOLD = "GOLD"
    SILVER = "SILVER"
    PLATINUM = "PLATINUM"
    PALLADIUM = "PALLADIUM"


COMMODITY_SYMBOLS = {
    CommodityType.GOLD: "XAU",
    CommodityType.SILVER: "XAG",
    CommodityType.PLATINUM: "XPT",
    CommodityType.PALLADIUM: "XPD",
}


class WeightUnit(str, Enum):
    GRAM = "GRAM"
    TROY_OUNCE = "TROY_OUNCE"


WEIGHT_CONVERSIONS = {
    WeightUnit.GRAM: {WeightUnit.TROY_OUNCE: Dezimal("0.032150746568628")},
    WeightUnit.TROY_OUNCE: {WeightUnit.GRAM: Dezimal("31.1034768")},
}


@dataclass
class CommodityRegister:
    name: str
    type: CommodityType
    amount: Dezimal
    unit: WeightUnit
    market_value: Optional[Dezimal] = None
    initial_investment: Optional[Dezimal] = None
    average_buy_price: Optional[Dezimal] = None
    currency: Optional[str] = None


@dataclass
class UpdateCommodityPosition:
    registers: list[CommodityRegister]
