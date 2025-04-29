from dataclasses import dataclass, field
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
    is_real: bool = True

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash(self.name)


class CredentialType(str, Enum):
    ID = "ID",
    USER = "USER",
    PASSWORD = "PASSWORD",
    PIN = "PIN",
    PHONE = "PHONE",
    EMAIL = "EMAIL",
    API_TOKEN = "API_TOKEN"


@dataclass(eq=False)
class NativeFinancialEntity(FinancialEntity):
    features: list[Feature] = field(default_factory=list)
    pin: Optional[PinDetails] = None
    credentials_template: dict[str, CredentialType] = field(default_factory=dict)


EntityCredentials = dict[str, str]
