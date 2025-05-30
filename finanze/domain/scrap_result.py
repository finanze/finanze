from dataclasses import field
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic.dataclasses import dataclass

from domain.entity_login import LoginResultCode, TwoFactor, LoginOptions
from domain.financial_entity import Feature
from domain.scraped_data import ScrapedData, VirtuallyScrapedData


class ScrapResultCode(str, Enum):
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
class ScrapRequest:
    entity_id: UUID
    features: list[Feature]
    two_factor: Optional[TwoFactor] = None
    options: Optional[LoginOptions] = field(default_factory=LoginOptions)


@dataclass
class ScrapResult:
    code: ScrapResultCode
    data: Optional[ScrapedData | VirtuallyScrapedData] = None
    details: Optional[dict] = None


SCRAP_BAD_LOGIN_CODES = {
    LoginResultCode.INVALID_CODE: ScrapResultCode.INVALID_CODE,
    LoginResultCode.INVALID_CREDENTIALS: ScrapResultCode.INVALID_CREDENTIALS,
    LoginResultCode.LOGIN_REQUIRED: ScrapResultCode.LOGIN_REQUIRED,
    LoginResultCode.MANUAL_LOGIN: ScrapResultCode.MANUAL_LOGIN,
    LoginResultCode.NO_CREDENTIALS_AVAILABLE: ScrapResultCode.NO_CREDENTIALS_AVAILABLE,
    LoginResultCode.UNEXPECTED_ERROR: ScrapResultCode.UNEXPECTED_LOGIN_ERROR,
    LoginResultCode.NOT_LOGGED: ScrapResultCode.NOT_LOGGED,
}
