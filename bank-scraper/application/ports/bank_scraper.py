import abc
from typing import Optional

from domain.auto_contributions import AutoContributions
from domain.bank_data import BankGlobalPosition
from domain.exceptions import FeatureNotSupported
from domain.transactions import Transactions


class BankScraper(metaclass=abc.ABCMeta):
    def login(self, credentials: tuple, **kwargs) -> Optional[dict]:
        raise NotImplementedError

    async def global_position(self) -> BankGlobalPosition:
        raise FeatureNotSupported

    async def auto_contributions(self) -> AutoContributions:
        raise FeatureNotSupported

    async def transactions(self, registered_txs: set[str]) -> Transactions:
        raise FeatureNotSupported
