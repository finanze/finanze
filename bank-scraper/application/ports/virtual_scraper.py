import abc
from typing import Optional

from domain.global_position import GlobalPosition
from domain.transactions import Transactions


class VirtualScraper(metaclass=abc.ABCMeta):
    async def global_positions(self, investment_sheets) -> dict[str, GlobalPosition]:
        raise NotImplementedError

    async def transactions(self, txs_sheets, registered_txs: set[str]) -> Optional[Transactions]:
        raise NotImplementedError
