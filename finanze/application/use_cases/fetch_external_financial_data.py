import logging
from asyncio import Lock
from datetime import datetime
from typing import List
from uuid import UUID

from application.ports.entity_port import EntityPort
from application.ports.external_entity_fetcher import (
    ExternalEntityFetcher,
)
from application.ports.external_entity_port import ExternalEntityPort
from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.last_fetches_port import LastFetchesPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.use_cases.fetch_financial_data import handle_cooldown
from dateutil.tz import tzlocal
from domain.entity import EntityOrigin, Feature
from domain.exception.exceptions import (
    EntityNotFound,
    ExecutionConflict,
    ExternalEntityFailed,
    ExternalEntityLinkExpired,
)
from domain.external_entity import (
    ExternalEntityFetchRequest,
    ExternalEntityStatus,
    ExternalFetchRequest,
)
from domain.external_integration import (
    ExternalIntegrationId,
    ExternalIntegrationType,
)
from domain.fetch_record import FetchRecord
from domain.fetch_result import (
    FetchedData,
    FetchResult,
    FetchResultCode,
)
from domain.use_cases.fetch_external_financial_data import FetchExternalFinancialData


class FetchExternalFinancialDataImpl(FetchExternalFinancialData):
    EXTERNALLY_PROVIDED_POSITION_UPDATE_COOLDOWN = 7200

    def __init__(
        self,
        entity_port: EntityPort,
        external_entity_port: ExternalEntityPort,
        position_port: PositionPort,
        external_entity_fetchers: dict[ExternalIntegrationId, ExternalEntityFetcher],
        external_integration_port: ExternalIntegrationPort,
        last_fetches_port: LastFetchesPort,
        transaction_handler_port: TransactionHandlerPort,
    ):
        self._entity_port = entity_port
        self._external_entity_port = external_entity_port
        self._position_port = position_port
        self._external_entity_fetchers = external_entity_fetchers
        self._external_integration_port = external_integration_port
        self._last_fetches_port = last_fetches_port
        self._transaction_handler_port = transaction_handler_port

        self._lock = Lock()

        self._log = logging.getLogger(__name__)

    async def execute(self, fetch_request: ExternalFetchRequest) -> FetchResult:
        external_entity_id = fetch_request.external_entity_id
        external_entity = await self._external_entity_port.get_by_id(external_entity_id)
        if not external_entity:
            raise EntityNotFound(external_entity_id)

        entity_id = external_entity.entity_id

        entity = await self._entity_port.get_by_id(entity_id)
        if not entity or entity.origin != EntityOrigin.EXTERNALLY_PROVIDED:
            raise EntityNotFound(entity_id)

        if self._lock.locked():
            raise ExecutionConflict()

        async with self._lock:
            last_fetch = await self._last_fetches_port.get_by_entity_id(entity_id)
            result = handle_cooldown(
                last_fetch, self.EXTERNALLY_PROVIDED_POSITION_UPDATE_COOLDOWN
            )
            if result:
                return result

            external_entity_provider = external_entity.provider
            provider = self._external_entity_fetchers[external_entity_provider]

            enabled_integrations = (
                await self._external_integration_port.get_payloads_by_type(
                    ExternalIntegrationType.ENTITY_PROVIDER
                )
            )
            await provider.setup(enabled_integrations)

            try:
                fetch_request = ExternalEntityFetchRequest(
                    external_entity=external_entity,
                    entity=entity,
                )
                position = await provider.global_position(fetch_request)

                async with self._transaction_handler_port.start():
                    if position:
                        await self._position_port.save(position)

                    await self._update_last_fetch(entity_id, [Feature.POSITION])

                    return FetchResult(
                        FetchResultCode.COMPLETED, data=FetchedData(position=position)
                    )

            except ExternalEntityFailed:
                return FetchResult(FetchResultCode.REMOTE_FAILED)
            except ExternalEntityLinkExpired:
                await self._external_entity_port.update_status(
                    external_entity_id, ExternalEntityStatus.UNLINKED
                )
                return FetchResult(FetchResultCode.LINK_EXPIRED)

    async def _update_last_fetch(self, entity_id: UUID, features: List[Feature]):
        now = datetime.now(tzlocal())
        records = []
        for feature in features:
            records.append(FetchRecord(entity_id=entity_id, feature=feature, date=now))
        await self._last_fetches_port.save(records)
