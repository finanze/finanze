from dataclasses import dataclass
from enum import Enum
from typing import Optional


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
    id: int
    name: str
    features: Optional[list[Feature]] = None
    pin: Optional[PinDetails] = None
    is_real: bool = True

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash(self.id)


MY_INVESTOR = FinancialEntity(
    id=1,
    name="MyInvestor",
    features=[Feature.POSITION, Feature.AUTO_CONTRIBUTIONS, Feature.TRANSACTIONS],
)

UNICAJA = FinancialEntity(
    id=2,
    name="Unicaja",
    features=[Feature.POSITION],
)

TRADE_REPUBLIC = FinancialEntity(
    id=3,
    name="Trade Republic",
    features=[Feature.POSITION, Feature.TRANSACTIONS],
    pin=PinDetails(positions=4),
)

URBANITAE = FinancialEntity(
    id=4,
    name="Urbanitae",
    features=[Feature.POSITION, Feature.TRANSACTIONS, Feature.HISTORIC],
)

WECITY = FinancialEntity(
    id=5,
    name="Wecity",
    features=[Feature.POSITION, Feature.TRANSACTIONS, Feature.HISTORIC],
    pin=PinDetails(positions=6),
)

SEGO = FinancialEntity(
    id=6,
    name="SEGO",
    features=[Feature.POSITION, Feature.TRANSACTIONS, Feature.HISTORIC],
    pin=PinDetails(positions=6),
)

MINTOS = FinancialEntity(
    id=7,
    name="Mintos",
    features=[Feature.POSITION],
)

F24 = FinancialEntity(
    id=8,
    name="Freedom24",
    features=[Feature.POSITION],
)

NATIVE_ENTITIES = [
    MY_INVESTOR,
    UNICAJA,
    TRADE_REPUBLIC,
    URBANITAE,
    WECITY,
    SEGO,
    MINTOS,
    F24
]
