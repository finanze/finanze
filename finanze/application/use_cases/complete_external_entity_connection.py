import logging

from application.ports.config_port import ConfigPort
from application.ports.external_entity_fetcher import ExternalEntityFetcher
from application.ports.external_entity_port import ExternalEntityPort
from application.use_cases.fetch_external_financial_data import (
    external_entity_provider_integrations_from_config,
)
from domain.exception.exceptions import ExternalEntityLinkError, ExternalEntityNotFound
from domain.external_entity import (
    CompleteExternalEntityLinkRequest,
    ExternalEntityStatus,
)
from domain.external_integration import ExternalIntegrationId
from domain.use_cases.complete_external_entity_connection import (
    CompleteExternalEntityConnection,
)


class CompleteExternalEntityConnectionImpl(CompleteExternalEntityConnection):
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

    async def execute(self, request: CompleteExternalEntityLinkRequest):
        is_error = "error" in request.payload
        if is_error:
            details = (
                request.payload.get("details")[0]
                if "details" in request.payload and request.payload.get("details")
                else {}
            )
            self._log.error(
                "Error completing external entity connection: %s",
                details,
            )
            raise ExternalEntityLinkError(details=details)

        is_callback = "ref" in request.payload or bool(request.payload.get("ref"))
        if not request.external_entity_id and not is_callback:
            raise ValueError("Missing 'ref' or 'external_entity_id'")

        external_entity_id = request.external_entity_id or request.payload.get("ref")[0]
        external_entity = self._external_entity_port.get_by_id(external_entity_id)
        if not external_entity:
            raise ExternalEntityNotFound()

        if external_entity.status == ExternalEntityStatus.LINKED:
            return

        provider = self._external_entity_fetchers.get(external_entity.provider)
        provider.setup(
            external_entity_provider_integrations_from_config(
                self._config_port.load().integrations
            ),
        )
        is_linked = await provider.is_linked(external_entity.provider_instance_id)
        if not is_callback and not is_linked:
            raise ExternalEntityLinkError(details="Entity noy properly linked.")

        external_entity.status = ExternalEntityStatus.LINKED

        self._external_entity_port.upsert(external_entity)
