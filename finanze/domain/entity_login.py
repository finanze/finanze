from dataclasses import field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic.dataclasses import dataclass

from domain.native_entity import EntityCredentials


class LoginResultCode(str, Enum):
    # Success
    CREATED = "CREATED"
    RESUMED = "RESUMED"

    # Flow deferral
    CODE_REQUESTED = "CODE_REQUESTED"
    MANUAL_LOGIN = "MANUAL_LOGIN"

    # Flow not completed (expected)
    NOT_LOGGED = "NOT_LOGGED"

    # Bad user input
    INVALID_CODE = "INVALID_CODE"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"

    # Not setup
    NO_CREDENTIALS_AVAILABLE = "NO_CREDENTIALS_AVAILABLE"

    # Error
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    UNEXPECTED_ERROR = "UNEXPECTED_LOGIN_ERROR"


@dataclass
class EntitySession:
    creation: datetime
    expiration: Optional[datetime]
    payload: dict


@dataclass
class EntityLoginResult:
    code: LoginResultCode
    message: Optional[str] = None
    details: Optional[dict] = None
    process_id: Optional[str] = None
    session: Optional[EntitySession] = None


@dataclass
class TwoFactor:
    code: Optional[str] = None
    process_id: Optional[str] = None


@dataclass
class LoginOptions:
    avoid_new_login: bool = False
    force_new_session: bool = False


@dataclass
class EntityLoginRequest:
    entity_id: UUID
    credentials: EntityCredentials
    two_factor: Optional[TwoFactor] = None
    options: Optional[LoginOptions] = field(default_factory=LoginOptions)


@dataclass
class EntityLoginParams:
    credentials: EntityCredentials
    two_factor: Optional[TwoFactor] = None
    options: Optional[LoginOptions] = field(default_factory=LoginOptions)
    session: Optional[EntitySession] = None


@dataclass
class EntityDisconnectRequest:
    entity_id: UUID
