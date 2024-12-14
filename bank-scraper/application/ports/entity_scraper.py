import abc
from typing import Optional

from domain.auto_contributions import AutoContributions
from domain.global_position import GlobalPosition
from domain.exceptions import FeatureNotSupported
from domain.transactions import Transactions


class EntityScraper(metaclass=abc.ABCMeta):
    def login(self, credentials: tuple, **kwargs) -> Optional[dict]:
        raise NotImplementedError

    async def global_position(self) -> GlobalPosition:
        raise FeatureNotSupported

    async def auto_contributions(self) -> AutoContributions:
        raise FeatureNotSupported

    async def transactions(self, registered_txs: set[str]) -> Transactions:
        raise FeatureNotSupported
