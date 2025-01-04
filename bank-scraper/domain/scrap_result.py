from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union

from domain.scraped_data import ScrapedData, VirtuallyScrapedData


class ScrapResultCode(str, Enum):
    COMPLETED = "COMPLETED"
    COOLDOWN = "COOLDOWN"
    DISABLED = "DISABLED"

    # Login related codes
    CODE_REQUESTED = "CODE_REQUESTED"
    INVALID_CODE = "INVALID_CODE"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    UNEXPECTED_LOGIN_ERROR = "UNEXPECTED_LOGIN_ERROR"
    NOT_LOGGED = "NOT_LOGGED"


class LoginResult(Enum):
    CREATED = "CREATED"
    RESUMED = "RESUMED"
    CODE_REQUESTED = "CODE_REQUESTED"
    INVALID_CODE = "INVALID_CODE"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
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
    LoginResult.UNEXPECTED_ERROR: ScrapResultCode.UNEXPECTED_LOGIN_ERROR,
    LoginResult.NOT_LOGGED: ScrapResultCode.NOT_LOGGED,
}
