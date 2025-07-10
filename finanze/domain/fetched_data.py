from typing import Optional

from pydantic.dataclasses import dataclass

from domain.auto_contributions import AutoContributions
from domain.global_position import GlobalPosition
from domain.historic import Historic
from domain.transactions import Transactions


@dataclass
class FetchedData:
    position: Optional[GlobalPosition] = None
    auto_contributions: Optional[AutoContributions] = None
    transactions: Optional[Transactions] = None
    historic: Optional[Historic] = None


@dataclass
class VirtuallyFetchedData:
    positions: Optional[list[GlobalPosition]] = None
    transactions: Optional[Transactions] = None
