import abc
from typing import Optional

from domain.auto_contributions import AutoContributions
from domain.bank_data import BankGlobalPosition


class BankScraper(metaclass=abc.ABCMeta):
    def login(self, credentials: tuple, **kwargs) -> Optional[dict]:
        raise NotImplementedError

    async def global_position(self) -> BankGlobalPosition:
        raise NotImplementedError

    async def auto_contributions(self) -> AutoContributions:
        raise NotImplementedError

    async def transactions(self):
        raise NotImplementedError
