from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from domain.entity import Entity, EntityType, Feature
from domain.external_integration import (
    ExternalIntegrationId,
)
from pydantic.dataclasses import dataclass


class ExternalEntityStatus(str, Enum):
    UNLINKED = "UNLINKED"
    LINKED = "LINKED"
    ORPHAN = "ORPHAN"


@dataclass
class ExternalEntity:
    id: UUID
    entity_id: UUID
    status: ExternalEntityStatus
    provider: ExternalIntegrationId
    date: Optional[datetime] = None
    provider_instance_id: Optional[str] = None
    payload: Optional[dict] = None


EXTERNAL_ENTITY_FEATURES = [Feature.POSITION]


@dataclass
class ProviderExternalEntityDetails:
    id: str
    name: str
    bic: str
    type: EntityType
    icon: Optional[str]


@dataclass
class ExternalEntityCandidates:
    entities: list[ProviderExternalEntityDetails]


@dataclass
class ExternalEntityCandidatesQuery:
    providers: Optional[list[ExternalIntegrationId]]
    country: Optional[str]


@dataclass
class ExternalEntityLoginRequest:
    external_entity: ExternalEntity
    redirect_host: Optional[str] = None
    relink: bool = False
    institution_id: Optional[str] = None
    user_language: Optional[str] = None


@dataclass
class ExternalEntityFetchRequest:
    external_entity: ExternalEntity
    entity: Entity


class ExternalEntitySetupResponseCode(str, Enum):
    ALREADY_LINKED = "ALREADY_LINKED"
    CONTINUE_WITH_LINK = "CONTINUE_WITH_LINK"


@dataclass
class ExternalEntityConnectionResult:
    code: ExternalEntitySetupResponseCode
    link: Optional[str] = None
    provider_instance_id: Optional[str] = None
    payload: Optional[Any] = None
    id: Optional[UUID] = None


@dataclass
class ExternalFetchRequest:
    external_entity_id: UUID


@dataclass
class ConnectExternalEntityRequest:
    institution_id: Optional[str]
    external_entity_id: Optional[UUID]
    provider: Optional[ExternalIntegrationId]
    relink: bool = False
    redirect_host: Optional[str] = None
    user_language: Optional[str] = None


@dataclass
class CompleteExternalEntityLinkRequest:
    payload: Optional[dict] = None
    external_entity_id: Optional[str] = None


@dataclass
class DeleteExternalEntityRequest:
    external_entity_id: UUID
