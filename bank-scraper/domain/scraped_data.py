from typing import Optional

from pydantic.dataclasses import dataclass

from domain.auto_contributions import AutoContributions
from domain.global_position import GlobalPosition
from domain.historic import Historic
from domain.transactions import Transactions


@dataclass
class ScrapedData:
    position: Optional[GlobalPosition] = None
    autoContributions: Optional[AutoContributions] = None
    transactions: Optional[Transactions] = None
    historic: Optional[Historic] = None


@dataclass
class VirtuallyScrapedData:
    positions: Optional[dict[str, GlobalPosition]] = None
    transactions: Optional[Transactions] = None
