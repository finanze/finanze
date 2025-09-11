import logging

from application.ports.config_port import ConfigPort
from application.ports.external_entity_fetcher import ExternalEntityFetcher
from application.ports.external_entity_port import ExternalEntityPort
from application.use_cases.fetch_external_financial_data import (
    external_entity_provider_integrations_from_config,
)
from domain.exception.exceptions import ExternalEntityNotFound
from domain.external_entity import (
    DeleteExternalEntityRequest,
)
from domain.external_integration import ExternalIntegrationId
from domain.use_cases.delete_external_entity import DeleteExternalEntity


class DeleteExternalEntityImpl(DeleteExternalEntity):
    def __init__(
        self,
        external_entity_port: ExternalEntityPort,
        external_entity_fetchers: dict[ExternalIntegrationId, ExternalEntityFetcher],
        config_port: ConfigPort,
    ):
        self._external_entity_port = external_entity_port
        self._external_entity_fetchers = external_entity_fetchers
        self._config_port = config_port

        self._log = logging.getLogger(__name__)

    async def execute(self, request: DeleteExternalEntityRequest):
        external_entity = self._external_entity_port.get_by_id(
            request.external_entity_id
        )
        if not external_entity:
            raise ExternalEntityNotFound()

        provider = self._external_entity_fetchers.get(external_entity.provider)
        provider.setup(
            external_entity_provider_integrations_from_config(
                self._config_port.load().integrations
            ),
        )

        try:
            await provider.unlink(external_entity.provider_instance_id)
        except ExternalEntityNotFound:
            self._log.warning(
                f"External entity {external_entity.id} not found at provider during unlinking."
            )
        self._external_entity_port.delete_by_id(external_entity.id)
