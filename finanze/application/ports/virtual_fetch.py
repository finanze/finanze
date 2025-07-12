import abc

from domain.entity import Entity
from domain.settings import (
    GoogleCredentials,
    VirtualPositionSheetConfig,
    VirtualTransactionSheetConfig,
)
from domain.virtual_fetch_result import VirtualPositionResult, VirtualTransactionResult


class VirtualFetcher(metaclass=abc.ABCMeta):
    async def global_positions(
        self,
        credentials: GoogleCredentials,
        investment_sheets: list[VirtualPositionSheetConfig],
        existing_entities: dict[str, Entity],
    ) -> VirtualPositionResult:
        raise NotImplementedError

    async def transactions(
        self,
        credentials: GoogleCredentials,
        txs_sheets: list[VirtualTransactionSheetConfig],
        existing_entities: dict[str, Entity],
    ) -> VirtualTransactionResult:
        raise NotImplementedError
