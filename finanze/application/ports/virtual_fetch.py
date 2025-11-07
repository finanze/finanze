import abc

from domain.entity import Entity
from domain.external_integration import ExternalIntegrationPayload
from domain.settings import (
    VirtualPositionSheetConfig,
    VirtualTransactionSheetConfig,
)
from domain.virtual_fetch_result import VirtualPositionResult, VirtualTransactionResult


class VirtualFetcher(metaclass=abc.ABCMeta):
    async def global_positions(
        self,
        credentials: ExternalIntegrationPayload,
        investment_sheets: list[VirtualPositionSheetConfig],
        existing_entities: dict[str, Entity],
    ) -> VirtualPositionResult:
        raise NotImplementedError

    async def transactions(
        self,
        credentials: ExternalIntegrationPayload,
        txs_sheets: list[VirtualTransactionSheetConfig],
        existing_entities: dict[str, Entity],
    ) -> VirtualTransactionResult:
        raise NotImplementedError
