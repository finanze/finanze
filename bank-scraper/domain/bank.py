from dataclasses import dataclass
from enum import Enum


class Bank(str, Enum):
    MY_INVESTOR = "MY_INVESTOR",
    UNICAJA = "UNICAJA",
    TRADE_REPUBLIC = "TRADE_REPUBLIC"
    URBANITAE = "URBANITAE"
    WECITY = "WECITY"
    SEGO = "SEGO"


class BankFeature(Enum):
    POSITION = "POSITION",
    AUTO_CONTRIBUTIONS = "AUTO_CONTRIBUTIONS",
    TRANSACTIONS = "TRANSACTIONS"


@dataclass
class BankInfo:
    name: str
