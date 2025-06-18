from dataclasses import field
from enum import Enum
from typing import Optional
from uuid import UUID

from domain.entity_login import LoginOptions, LoginResultCode, TwoFactor
from domain.entity import Feature
from domain.fetched_data import FetchedData, VirtuallyFetchedData
from pydantic.dataclasses import dataclass


class FetchResultCode(str, Enum):
    # Success
    COMPLETED = "COMPLETED"

    # Cooldown
    COOLDOWN = "COOLDOWN"

    # Bad user input
    ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND"
    FEATURE_NOT_SUPPORTED = "FEATURE_NOT_SUPPORTED"

    # Entity or feature disabled (also bad input)
    DISABLED = "DISABLED"

    # Login related codes
    CODE_REQUESTED = "CODE_REQUESTED"
    MANUAL_LOGIN = "MANUAL_LOGIN"
    NOT_LOGGED = "NOT_LOGGED"
    INVALID_CODE = "INVALID_CODE"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    NO_CREDENTIALS_AVAILABLE = "NO_CREDENTIALS_AVAILABLE"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    UNEXPECTED_LOGIN_ERROR = "UNEXPECTED_LOGIN_ERROR"


@dataclass
class FetchOptions:
    deep: bool = False


@dataclass
class FetchRequest:
    entity_id: UUID
    features: list[Feature]
    two_factor: Optional[TwoFactor] = None
    login_options: Optional[LoginOptions] = field(default_factory=LoginOptions)
    fetch_options: Optional[FetchOptions] = field(default_factory=FetchOptions)


@dataclass
class FetchResult:
    code: FetchResultCode
    data: Optional[FetchedData | VirtuallyFetchedData] = None
    details: Optional[dict] = None


FETCH_BAD_LOGIN_CODES = {
    LoginResultCode.INVALID_CODE: FetchResultCode.INVALID_CODE,
    LoginResultCode.INVALID_CREDENTIALS: FetchResultCode.INVALID_CREDENTIALS,
    LoginResultCode.LOGIN_REQUIRED: FetchResultCode.LOGIN_REQUIRED,
    LoginResultCode.MANUAL_LOGIN: FetchResultCode.MANUAL_LOGIN,
    LoginResultCode.NO_CREDENTIALS_AVAILABLE: FetchResultCode.NO_CREDENTIALS_AVAILABLE,
    LoginResultCode.UNEXPECTED_ERROR: FetchResultCode.UNEXPECTED_LOGIN_ERROR,
    LoginResultCode.NOT_LOGGED: FetchResultCode.NOT_LOGGED,
}
