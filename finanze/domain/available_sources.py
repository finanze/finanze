from datetime import datetime
from enum import Enum
from typing import Optional

from domain.crypto import CryptoWalletConnection
from domain.entity import (
    CredentialType,
    Entity,
    EntitySetupLoginType,
    Feature,
    PinDetails,
)
from domain.external_integration import ExternalIntegrationId
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
    credentials_template: Optional[dict[str, CredentialType]] = None
    pin: Optional[PinDetails] = None
    status: Optional[FinancialEntityStatus] = None
    connected: Optional[list[CryptoWalletConnection]] = None
    required_external_integrations: list[ExternalIntegrationId] = None


@dataclass
class AvailableSources:
    entities: list[AvailableSource]
