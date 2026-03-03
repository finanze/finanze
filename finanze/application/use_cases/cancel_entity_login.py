import logging
from uuid import UUID

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from domain import native_entities
from domain.entity import Entity, EntityType
from domain.use_cases.cancel_entity_login import CancelEntityLogin


class CancelEntityLoginImpl(CancelEntityLogin):
    def __init__(self, entity_fetchers: dict[Entity, FinancialEntityFetcher]):
        self._entity_fetchers = entity_fetchers
        self._log = logging.getLogger(__name__)

    def execute(self, entity_id: UUID) -> None:
        entity = native_entities.get_native_by_id(
            entity_id, EntityType.FINANCIAL_INSTITUTION, EntityType.CRYPTO_EXCHANGE
        )
        if not entity:
            return

        fetcher = self._entity_fetchers.get(entity)
        if fetcher:
            fetcher.cancel_login()
