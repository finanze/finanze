from dataclasses import field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from domain.crypto import CryptoWalletConnection
from domain.entity import (
    Entity,
    Feature,
)
from domain.native_entity import (
    PinDetails,
    CredentialType,
    EntitySetupLoginType,
    EntitySessionCategory,
)
from domain.external_integration import ExternalIntegrationId
from domain.global_position import ProductType
from pydantic.dataclasses import dataclass


class FinancialEntityStatus(str, Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    REQUIRES_LOGIN = "REQUIRES_LOGIN"


@dataclass(eq=False)
class AvailableSource(Entity):
    features: list[Feature]
    last_fetch: dict[Feature, datetime]
    setup_login_type: Optional[EntitySetupLoginType] = None
    session_category: Optional[EntitySessionCategory] = None
    credentials_template: Optional[dict[str, CredentialType]] = None
    pin: Optional[PinDetails] = None
    status: Optional[FinancialEntityStatus] = None
    connected: Optional[list[CryptoWalletConnection]] = None
    required_external_integrations: list[ExternalIntegrationId] = field(
        default_factory=list
    )
    external_entity_id: Optional[UUID] = None
    virtual_features: dict[Feature, datetime] = field(default_factory=dict)
    natively_supported_products: Optional[list[ProductType]] = None
    fetchable: bool = True


@dataclass
class AvailableSources:
    entities: list[AvailableSource]
