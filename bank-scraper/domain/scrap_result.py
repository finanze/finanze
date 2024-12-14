from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union

from domain.scraped_data import ScrapedData, VirtuallyScrapedData


class ScrapResultCode(str, Enum):
    CODE_REQUESTED = "CODE_REQUESTED"
    NOT_LOGGED = "NOT_LOGGED"
    COMPLETED = "COMPLETED"
    COOLDOWN = "COOLDOWN"


@dataclass
class ScrapResult:
    code: ScrapResultCode
    data: Optional[Union[ScrapedData, VirtuallyScrapedData]] = None
    details: Optional[dict] = None
