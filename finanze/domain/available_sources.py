from enum import Enum
from typing import Optional

from domain.entity import (
    CredentialType,
    Entity,
    EntitySetupLoginType,
    Feature,
    PinDetails,
)
from pydantic.dataclasses import dataclass


class FinancialEntityStatus(str, Enum):
    CONNECTED = ("CONNECTED",)
    DISCONNECTED = ("DISCONNECTED",)
    REQUIRES_LOGIN = ("REQUIRES_LOGIN",)


@dataclass(eq=False)
class AvailableFinancialEntity(Entity):
    features: list[Feature]
    setup_login_type: Optional[EntitySetupLoginType] = None
    credentials_template: Optional[dict[str, CredentialType]] = None
    pin: Optional[PinDetails] = None
    status: FinancialEntityStatus = FinancialEntityStatus.DISCONNECTED


@dataclass
class AvailableSources:
    virtual: bool
    entities: list[AvailableFinancialEntity]
