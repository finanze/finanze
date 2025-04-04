from enum import Enum
from typing import Optional, Union

from pydantic.dataclasses import dataclass

from domain.scraped_data import ScrapedData, VirtuallyScrapedData


class ScrapResultCode(str, Enum):
    COMPLETED = "COMPLETED"
    COOLDOWN = "COOLDOWN"
    DISABLED = "DISABLED"
    ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND"
    FEATURE_NOT_SUPPORTED = "FEATURE_NOT_SUPPORTED"

    # Login related codes
    CODE_REQUESTED = "CODE_REQUESTED"
    INVALID_CODE = "INVALID_CODE"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    NO_CREDENTIALS_AVAILABLE = "NO_CREDENTIALS_AVAILABLE"
    UNEXPECTED_LOGIN_ERROR = "UNEXPECTED_LOGIN_ERROR"
    NOT_LOGGED = "NOT_LOGGED"


class LoginResult(Enum):
    CREATED = "CREATED"
    RESUMED = "RESUMED"
    CODE_REQUESTED = "CODE_REQUESTED"
    INVALID_CODE = "INVALID_CODE"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    NO_CREDENTIALS_AVAILABLE = "NO_CREDENTIALS_AVAILABLE"
    UNEXPECTED_ERROR = "UNEXPECTED_LOGIN_ERROR"
    NOT_LOGGED = "NOT_LOGGED"


@dataclass
class ScrapResult:
    code: ScrapResultCode
    data: Optional[Union[ScrapedData, VirtuallyScrapedData]] = None
    details: Optional[dict] = None


SCRAP_BAD_LOGIN_CODES = {
    LoginResult.INVALID_CODE: ScrapResultCode.INVALID_CODE,
    LoginResult.INVALID_CREDENTIALS: ScrapResultCode.INVALID_CREDENTIALS,
    LoginResult.NO_CREDENTIALS_AVAILABLE: ScrapResultCode.NO_CREDENTIALS_AVAILABLE,
    LoginResult.UNEXPECTED_ERROR: ScrapResultCode.UNEXPECTED_LOGIN_ERROR,
    LoginResult.NOT_LOGGED: ScrapResultCode.NOT_LOGGED,
}
