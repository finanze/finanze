import logging

from application.ports.external_entity_fetcher import ExternalEntityFetcher
from application.ports.external_entity_port import ExternalEntityPort
from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.last_fetches_port import LastFetchesPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_port import TransactionPort
from domain.exception.exceptions import ExternalEntityNotFound
from domain.external_entity import (
    DeleteExternalEntityRequest,
)
from domain.external_integration import ExternalIntegrationId, ExternalIntegrationType
from domain.fetch_record import DataSource
from domain.use_cases.delete_external_entity import DeleteExternalEntity


class DeleteExternalEntityImpl(DeleteExternalEntity):
    def __init__(
        self,
        external_entity_port: ExternalEntityPort,
        external_entity_fetchers: dict[ExternalIntegrationId, ExternalEntityFetcher],
        external_integration_port: ExternalIntegrationPort,
        transaction_port: TransactionPort,
        last_fetches_port: LastFetchesPort,
        transaction_handler_port: TransactionHandlerPort,
    ):
        self._external_entity_port = external_entity_port
        self._external_entity_fetchers = external_entity_fetchers
        self._external_integration_port = external_integration_port
        self._transaction_port = transaction_port
        self._last_fetches_port = last_fetches_port
        self._transaction_handler_port = transaction_handler_port

        self._log = logging.getLogger(__name__)

    async def execute(self, request: DeleteExternalEntityRequest):
        external_entity = await self._external_entity_port.get_by_id(
            request.external_entity_id
        )
        if not external_entity:
            raise ExternalEntityNotFound()

        provider = self._external_entity_fetchers.get(external_entity.provider)
        enabled_integrations = (
            await self._external_integration_port.get_payloads_by_type(
                ExternalIntegrationType.ENTITY_PROVIDER
            )
        )
        await provider.setup(enabled_integrations)

        try:
            await provider.unlink(external_entity.provider_instance_id)
        except ExternalEntityNotFound:
            self._log.warning(
                f"External entity {external_entity.id} not found at provider during unlinking."
            )

        async with self._transaction_handler_port.start():
            await self._transaction_port.delete_by_entity_and_source(
                external_entity.entity_id, DataSource.REAL
            )
            await self._last_fetches_port.delete_by_entity_id(external_entity.entity_id)
            await self._external_entity_port.delete_by_id(external_entity.id)
