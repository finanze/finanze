from dataclasses import dataclass
from enum import Enum
from typing import Optional

from domain.bank_data import BankData


class ScrapResultCode(Enum):
    CODE_REQUESTED = "CODE_REQUESTED"
    COMPLETED = "COMPLETED"


@dataclass
class ScrapResult:
    code: ScrapResultCode
    data: Optional[BankData] = None
    details: Optional[dict] = None
