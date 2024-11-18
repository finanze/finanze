from dataclasses import dataclass
from enum import Enum


class Bank(Enum):
    MY_INVESTOR = "MY_INVESTOR",
    UNICAJA = "UNICAJA",
    TRADE_REPUBLIC = "TRADE_REPUBLIC"


@dataclass
class BankInfo:
    name: str
