from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic.dataclasses import dataclass


class Feature(str, Enum):
    POSITION = "POSITION"
    AUTO_CONTRIBUTIONS = "AUTO_CONTRIBUTIONS"
    TRANSACTIONS = "TRANSACTIONS"
    HISTORIC = "HISTORIC"


class EntityType(str, Enum):
    FINANCIAL_INSTITUTION = "FINANCIAL_INSTITUTION"
    CRYPTO_WALLET = "CRYPTO_WALLET"
    CRYPTO_EXCHANGE = "CRYPTO_EXCHANGE"
    COMMODITY = "COMMODITY"


class EntityOrigin(str, Enum):
    MANUAL = "MANUAL"
    NATIVE = "NATIVE"
    EXTERNALLY_PROVIDED = "EXTERNALLY_PROVIDED"
    INTERNAL = "INTERNAL"


@dataclass
class Entity:
    id: Optional[UUID]
    name: str
    natural_id: Optional[str]
    type: EntityType
    origin: EntityOrigin
    icon_url: Optional[str]

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash(self.name)
