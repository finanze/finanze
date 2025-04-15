from enum import Enum
from typing import Optional, Union
from uuid import UUID

from pydantic.dataclasses import dataclass

from domain.financial_entity import Feature
from domain.login_result import LoginResultCode, TwoFactor, LoginOptions
from domain.scraped_data import ScrapedData, VirtuallyScrapedData


class ScrapResultCode(str, Enum):
    COMPLETED = "COMPLETED"
    COOLDOWN = "COOLDOWN"
    ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND"
    FEATURE_NOT_SUPPORTED = "FEATURE_NOT_SUPPORTED"

    # Login related codes
    CODE_REQUESTED = "CODE_REQUESTED"
    INVALID_CODE = "INVALID_CODE"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    NO_CREDENTIALS_AVAILABLE = "NO_CREDENTIALS_AVAILABLE"
    UNEXPECTED_LOGIN_ERROR = "UNEXPECTED_LOGIN_ERROR"
    NOT_LOGGED = "NOT_LOGGED"


@dataclass
class ScrapRequest:
    entity_id: UUID
    features: list[Feature]
    two_factor: Optional[TwoFactor] = None
    options: Optional[LoginOptions] = LoginOptions()


@dataclass
class ScrapResult:
    code: ScrapResultCode
    data: Optional[Union[ScrapedData, VirtuallyScrapedData]] = None
    details: Optional[dict] = None


SCRAP_BAD_LOGIN_CODES = {
    LoginResultCode.INVALID_CODE: ScrapResultCode.INVALID_CODE,
    LoginResultCode.INVALID_CREDENTIALS: ScrapResultCode.INVALID_CREDENTIALS,
    LoginResultCode.NO_CREDENTIALS_AVAILABLE: ScrapResultCode.NO_CREDENTIALS_AVAILABLE,
    LoginResultCode.UNEXPECTED_ERROR: ScrapResultCode.UNEXPECTED_LOGIN_ERROR,
    LoginResultCode.NOT_LOGGED: ScrapResultCode.NOT_LOGGED,
}
