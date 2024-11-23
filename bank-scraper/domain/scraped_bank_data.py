from dataclasses import dataclass
from typing import Optional

from domain.auto_contributions import AutoContributions
from domain.bank_data import BankGlobalPosition
from domain.transactions import Transactions


@dataclass
class ScrapedBankData:
    position: Optional[BankGlobalPosition] = None
    autoContributions: Optional[AutoContributions] = None
    transactions: Optional[Transactions] = None
