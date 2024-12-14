from dataclasses import dataclass
from typing import Optional

from domain.auto_contributions import AutoContributions
from domain.financial_entity import Entity
from domain.global_position import GlobalPosition
from domain.transactions import Transactions


@dataclass
class ScrapedData:
    position: Optional[GlobalPosition] = None
    autoContributions: Optional[AutoContributions] = None
    transactions: Optional[Transactions] = None


@dataclass
class VirtuallyScrapedData:
    positions: Optional[dict[str, GlobalPosition]] = None
    transactions: Optional[Transactions] = None
