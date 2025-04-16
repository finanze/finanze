from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic.dataclasses import dataclass

from domain.financial_entity import EntityCredentials


class LoginResultCode(str, Enum):
    CREATED = "CREATED"
    RESUMED = "RESUMED"
    CODE_REQUESTED = "CODE_REQUESTED"
    INVALID_CODE = "INVALID_CODE"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    NO_CREDENTIALS_AVAILABLE = "NO_CREDENTIALS_AVAILABLE"
    UNEXPECTED_ERROR = "UNEXPECTED_LOGIN_ERROR"
    NOT_LOGGED = "NOT_LOGGED"


@dataclass
class EntitySession:
    creation: datetime
    expiration: Optional[datetime]
    payload: dict


@dataclass
class LoginResult:
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
class LoginRequest:
    entity_id: UUID
    credentials: EntityCredentials
    two_factor: Optional[TwoFactor] = None
    options: Optional[LoginOptions] = LoginOptions()


@dataclass
class LoginParams:
    credentials: EntityCredentials
    two_factor: Optional[TwoFactor] = None
    options: Optional[LoginOptions] = LoginOptions()
    session: Optional[EntitySession] = None
