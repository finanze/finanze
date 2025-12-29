import logging

from application.ports.entity_port import EntityPort
from application.ports.external_entity_fetcher import (
    ExternalEntityFetcher,
)
from application.ports.external_entity_port import ExternalEntityPort
from application.ports.external_integration_port import ExternalIntegrationPort
from domain.entity import EntityOrigin
from domain.external_entity import (
    ExternalEntityCandidates,
    ExternalEntityCandidatesQuery,
)
from domain.external_integration import (
    ExternalIntegrationId,
    ExternalIntegrationType,
)
from domain.use_cases.get_available_external_entities import (
    GetAvailableExternalEntities,
)


class GetAvailableExternalEntitiesImpl(GetAvailableExternalEntities):
    DEFAULT_PROVIDER = ExternalIntegrationId.GOCARDLESS

    def __init__(
        self,
        entity_port: EntityPort,
        external_entity_port: ExternalEntityPort,
        external_entity_fetchers: dict[ExternalIntegrationId, ExternalEntityFetcher],
        external_integration_port: ExternalIntegrationPort,
    ):
        self._entity_port = entity_port
        self._external_entity_port = external_entity_port
        self._external_entity_fetchers = external_entity_fetchers
        self._external_integration_port = external_integration_port

        self._log = logging.getLogger(__name__)

    async def execute(
        self, request: ExternalEntityCandidatesQuery
    ) -> ExternalEntityCandidates:
        provider = self._external_entity_fetchers[self.DEFAULT_PROVIDER]

        setup_entities = self._entity_port.get_all()
        setup_entities_by_natural_ids = {e.natural_id: e for e in setup_entities}
        setup_external_entities_entity_ids = {
            ee.entity_id for ee in self._external_entity_port.get_all()
        }

        enabled_integrations = self._external_integration_port.get_payloads_by_type(
            ExternalIntegrationType.ENTITY_PROVIDER
        )
        provider.setup(enabled_integrations)

        all_candidates = await provider.get_entities(country=request.country)
        filtered_candidates = []
        for candidate in all_candidates:
            entity_by_natural_id = setup_entities_by_natural_ids.get(candidate.bic)
            if not entity_by_natural_id or (
                entity_by_natural_id.id not in setup_external_entities_entity_ids
                and entity_by_natural_id.origin != EntityOrigin.NATIVE
            ):
                filtered_candidates.append(candidate)

        return ExternalEntityCandidates(entities=filtered_candidates)
