from dataclasses import dataclass
from enum import Enum
from typing import Optional

from domain.scraped_bank_data import ScrapedBankData


class ScrapResultCode(Enum):
    CODE_REQUESTED = "CODE_REQUESTED"
    NOT_LOGGED = "NOT_LOGGED"
    COMPLETED = "COMPLETED"
    COOLDOWN = "COOLDOWN"


@dataclass
class ScrapResult:
    code: ScrapResultCode
    data: Optional[ScrapedBankData] = None
    details: Optional[dict] = None
