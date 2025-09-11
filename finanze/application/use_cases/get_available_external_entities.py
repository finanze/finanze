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
        setup_entities_natural_ids = {e.natural_id for e in setup_entities}

        provider.setup(
            external_entity_provider_integrations_from_config(
                self._config_port.load().integrations
            ),
        )

        candidates = await provider.get_entities(country=request.country)
        candidates = [c for c in candidates if c.bic not in setup_entities_natural_ids]

        return ExternalEntityCandidates(entities=candidates)
