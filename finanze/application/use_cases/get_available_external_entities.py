import logging

from application.ports.config_port import ConfigPort
from application.ports.entity_port import EntityPort
from application.ports.external_entity_fetcher import (
    ExternalEntityFetcher,
)
from application.ports.external_entity_port import ExternalEntityPort
from application.use_cases.fetch_external_financial_data import (
    external_entity_provider_integrations_from_config,
)
from domain.external_entity import (
    ExternalEntityCandidates,
    ExternalEntityCandidatesQuery,
)
from domain.external_integration import (
    ExternalIntegrationId,
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
        config_port: ConfigPort,
    ):
        self._entity_port = entity_port
        self._external_entity_port = external_entity_port
        self._external_entity_fetchers = external_entity_fetchers
        self._config_port = config_port

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

        provider.setup(
            external_entity_provider_integrations_from_config(
                self._config_port.load().integrations
            ),
        )

        all_candidates = await provider.get_entities(country=request.country)
        filtered_candidates = []
        for candidate in all_candidates:
            entity_by_natural_id = setup_entities_by_natural_ids.get(candidate.bic)
            if (
                not entity_by_natural_id
                or entity_by_natural_id.id not in setup_external_entities_entity_ids
            ):
                filtered_candidates.append(candidate)

        return ExternalEntityCandidates(entities=filtered_candidates)
