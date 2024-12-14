import abc

from domain.global_position import GlobalPosition
from domain.transactions import Transactions


class VirtualScraper(metaclass=abc.ABCMeta):
    async def global_positions(self) -> dict[str, GlobalPosition]:
        pass

    async def transactions(self, registered_txs: set[str]) -> Transactions:
        pass
