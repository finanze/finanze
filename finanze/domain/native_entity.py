from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic.dataclasses import dataclass

from domain.entity import Entity, Feature
from domain.external_integration import ExternalIntegrationId
from domain.global_position import ProductType


@dataclass
class PinDetails:
    positions: int


class CredentialType(str, Enum):
    ID = "ID"
    USER = "USER"
    PASSWORD = "PASSWORD"
    PIN = "PIN"
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    API_TOKEN = "API_TOKEN"

    # Internal usage (cookies, headers..., got from external login)
    INTERNAL = "INTERNAL"
    # Same but not persisted
    INTERNAL_TEMP = "INTERNAL_TEMP"


class EntitySetupLoginType(str, Enum):
    MANUAL = "MANUAL"
    AUTOMATED = "AUTOMATED"


class EntitySessionCategory(str, Enum):
    # No session requiring human action to re-create or minutes-long session
    NONE = "NONE"
    # Little hours-long session
    SHORT = "SHORT"
    # Some days-long session
    MEDIUM = "MEDIUM"
    # No session, renewable or weeks-long session
    UNDEFINED = "UNDEFINED"


@dataclass(eq=False)
class NativeFinancialEntity(Entity):
    setup_login_type: EntitySetupLoginType
    session_category: EntitySessionCategory
    credentials_template: dict[str, CredentialType]
    features: list[Feature]
    products: list[ProductType]
    pin: Optional[PinDetails] = None


@dataclass(eq=False)
class NativeCryptoWalletEntity(Entity):
    features: list[Feature]
    required_external_integrations: list[ExternalIntegrationId]


EntityCredentials = dict[str, str]


@dataclass
class FinancialEntityCredentialsEntry:
    entity_id: UUID
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    expiration: Optional[datetime] = None
