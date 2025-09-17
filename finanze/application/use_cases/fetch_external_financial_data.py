import logging
from asyncio import Lock
from datetime import datetime
from typing import List
from uuid import UUID

from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.config_port import ConfigPort
from application.ports.entity_port import EntityPort
from application.ports.external_entity_fetcher import (
    ExternalEntityFetcher,
)
from application.ports.external_entity_port import ExternalEntityPort
from application.ports.last_fetches_port import LastFetchesPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from dateutil.tz import tzlocal
from domain.entity import Entity, EntityOrigin, Feature
from domain.exception.exceptions import (
    EntityNotFound,
    ExecutionConflict,
    ExternalEntityFailed,
    ExternalEntityLinkExpired,
)
from domain.external_entity import (
    ExternalEntity,
    ExternalEntityFetchRequest,
    ExternalEntityProviderIntegrations,
    ExternalEntityStatus,
    ExternalFetchRequest,
)
from domain.external_integration import (
    ExternalIntegrationId,
    GoCardlessIntegrationCredentials,
)
from domain.fetch_record import FetchRecord
from domain.fetch_result import (
    FetchedData,
    FetchResult,
    FetchResultCode,
)
from domain.settings import IntegrationsConfig
from domain.use_cases.fetch_external_financial_data import FetchExternalFinancialData


def external_entity_provider_integrations_from_config(
    config: IntegrationsConfig,
) -> ExternalEntityProviderIntegrations:
    gocardless = None
    if config.gocardless:
        gocardless = GoCardlessIntegrationCredentials(
            secret_key=config.gocardless.secret_key,
            secret_id=config.gocardless.secret_id,
        )
    return ExternalEntityProviderIntegrations(gocardless=gocardless)


class FetchExternalFinancialDataImpl(AtomicUCMixin, FetchExternalFinancialData):
    EXTERNALLY_PROVIDED_POSITION_UPDATE_COOLDOWN = 7200

    def __init__(
        self,
        entity_port: EntityPort,
        external_entity_port: ExternalEntityPort,
        position_port: PositionPort,
        external_entity_fetchers: dict[ExternalIntegrationId, ExternalEntityFetcher],
        config_port: ConfigPort,
        last_fetches_port: LastFetchesPort,
        transaction_handler_port: TransactionHandlerPort,
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)

        self._entity_port = entity_port
        self._external_entity_port = external_entity_port
        self._position_port = position_port
        self._external_entity_fetchers = external_entity_fetchers
        self._config_port = config_port
        self._last_fetches_port = last_fetches_port

        self._lock = Lock()

        self._log = logging.getLogger(__name__)

    async def execute(self, fetch_request: ExternalFetchRequest) -> FetchResult:
        external_entity_id = fetch_request.external_entity_id
        external_entity = self._external_entity_port.get_by_id(external_entity_id)
        if not external_entity:
            raise EntityNotFound(external_entity_id)

        entity_id = external_entity.entity_id

        entity = self._entity_port.get_by_id(entity_id)
        if not entity or entity.origin != EntityOrigin.EXTERNALLY_PROVIDED:
            raise EntityNotFound(entity_id)

        if self._lock.locked():
            raise ExecutionConflict()

        async with self._lock:
            last_fetch = self._last_fetches_port.get_by_entity_id(entity_id)
            last_fetch = next(
                (record for record in last_fetch if record.feature == Feature.POSITION),
                None,
            )
            if last_fetch:
                last_fetch = last_fetch.date
            if (
                last_fetch
                and (datetime.now(tzlocal()) - last_fetch).seconds
                < self.EXTERNALLY_PROVIDED_POSITION_UPDATE_COOLDOWN
            ):
                remaining_seconds = (
                    self.EXTERNALLY_PROVIDED_POSITION_UPDATE_COOLDOWN
                    - (datetime.now(tzlocal()) - last_fetch).seconds
                )
                details = {
                    "lastUpdate": last_fetch.astimezone(tzlocal()).isoformat(),
                    "wait": remaining_seconds,
                }
                return FetchResult(FetchResultCode.COOLDOWN, details=details)

            external_entity_provider = external_entity.provider
            provider = self._external_entity_fetchers[external_entity_provider]

            provider.setup(
                external_entity_provider_integrations_from_config(
                    self._config_port.load().integrations
                ),
            )

            try:
                fetched_data = await self.get_data(provider, external_entity, entity)

            except ExternalEntityFailed:
                return FetchResult(FetchResultCode.REMOTE_FAILED)
            except ExternalEntityLinkExpired:
                self._external_entity_port.update_status(
                    external_entity_id, ExternalEntityStatus.UNLINKED
                )
                return FetchResult(FetchResultCode.LINK_EXPIRED)

            self._update_last_fetch(entity_id, [Feature.POSITION])

            return FetchResult(FetchResultCode.COMPLETED, data=fetched_data)

    async def get_data(
        self,
        provider: ExternalEntityFetcher,
        external_entity: ExternalEntity,
        entity: Entity,
    ) -> FetchedData:
        fetch_request = ExternalEntityFetchRequest(
            external_entity=external_entity,
            entity=entity,
        )

        position = await provider.global_position(fetch_request)

        if position:
            self._position_port.save(position)

        fetched_data = FetchedData(position=position)

        return fetched_data

    def _update_last_fetch(self, entity_id: UUID, features: List[Feature]):
        now = datetime.now(tzlocal())
        records = []
        for feature in features:
            records.append(FetchRecord(entity_id=entity_id, feature=feature, date=now))
        self._last_fetches_port.save(records)
