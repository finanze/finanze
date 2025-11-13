import abc

from domain.entity import Entity
from domain.external_integration import ExternalIntegrationPayload
from domain.settings import (
    ImportPositionSheetConfig,
    ImportTransactionsSheetConfig,
)
from domain.import_result import PositionImportResult, TransactionsImportResult


class VirtualFetcher(metaclass=abc.ABCMeta):
    async def global_positions(
        self,
        credentials: ExternalIntegrationPayload,
        investment_sheets: list[ImportPositionSheetConfig],
        existing_entities: dict[str, Entity],
    ) -> PositionImportResult:
        raise NotImplementedError

    async def transactions(
        self,
        credentials: ExternalIntegrationPayload,
        txs_sheets: list[ImportTransactionsSheetConfig],
        existing_entities: dict[str, Entity],
    ) -> TransactionsImportResult:
        raise NotImplementedError
