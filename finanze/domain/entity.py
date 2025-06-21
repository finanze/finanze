from datetime import datetime
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


@dataclass
class PinDetails:
    positions: int


@dataclass
class Entity:
    id: Optional[UUID]
    name: str
    type: EntityType
    is_real: bool

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash(self.name)


class CredentialType(str, Enum):
    ID = "ID"
    USER = "USER"
    PASSWORD = "PASSWORD"
    PIN = "PIN"
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    API_TOKEN = "API_TOKEN"

    # Internal usage (cookies, headers..., usually from external login)
    INTERNAL = "INTERNAL"
    INTERNAL_TEMP = "INTERNAL_TEMP"


class EntitySetupLoginType(str, Enum):
    MANUAL = "MANUAL"
    AUTOMATED = "AUTOMATED"


@dataclass(eq=False)
class NativeFinancialEntity(Entity):
    setup_login_type: EntitySetupLoginType
    credentials_template: dict[str, CredentialType]
    features: list[Feature]
    pin: Optional[PinDetails] = None


@dataclass(eq=False)
class NativeCryptoWalletEntity(Entity):
    features: list[Feature]


EntityCredentials = dict[str, str]


@dataclass
class FinancialEntityCredentialsEntry:
    entity_id: UUID
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    expiration: Optional[datetime] = None
