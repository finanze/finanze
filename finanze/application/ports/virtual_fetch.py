import abc
from typing import Optional

from domain.entity import Entity
from domain.global_position import GlobalPosition
from domain.settings import (
    GoogleCredentials,
    VirtualPositionSheetConfig,
    VirtualTransactionSheetConfig,
)
from domain.transactions import Transactions


class VirtualFetcher(metaclass=abc.ABCMeta):
    async def global_positions(
        self,
        credentials: GoogleCredentials,
        investment_sheets: list[VirtualPositionSheetConfig],
        existing_entities: dict[str, Entity],
    ) -> tuple[list[GlobalPosition], set[Entity]]:
        raise NotImplementedError

    async def transactions(
        self,
        credentials: GoogleCredentials,
        txs_sheets: list[VirtualTransactionSheetConfig],
        existing_entities: dict[str, Entity],
    ) -> tuple[Optional[Transactions], set[Entity]]:
        raise NotImplementedError
