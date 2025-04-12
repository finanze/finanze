from dataclasses import dataclass
from enum import Enum
from typing import Optional
from uuid import UUID


class Feature(str, Enum):
    POSITION = "POSITION",
    AUTO_CONTRIBUTIONS = "AUTO_CONTRIBUTIONS",
    TRANSACTIONS = "TRANSACTIONS"
    HISTORIC = "HISTORIC"


@dataclass
class PinDetails:
    positions: int


@dataclass
class FinancialEntity:
    id: Optional[UUID]
    name: str
    features: Optional[list[Feature]] = None
    pin: Optional[PinDetails] = None
    is_real: bool = True

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash(self.name)
