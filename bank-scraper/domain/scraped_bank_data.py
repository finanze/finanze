from dataclasses import dataclass
from typing import Optional

from domain.auto_contributions import AutoContributions
from domain.bank_data import BankGlobalPosition


@dataclass
class ScrapedBankData:
    position: Optional[BankGlobalPosition] = None
    autoContributions: Optional[AutoContributions] = None
