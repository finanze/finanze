from dataclasses import asdict

from application.ports.config_port import ConfigPort
from application.ports.credentials_port import CredentialsPort
from domain.available_sources import AvailableSources, AvailableFinancialEntity
from domain.native_entities import NATIVE_ENTITIES
from domain.use_cases.get_available_entities import GetAvailableEntities


class GetAvailableEntitiesImpl(GetAvailableEntities):

    def __init__(self,
                 config_port: ConfigPort,
                 credentials_port: CredentialsPort):
        self._config_port = config_port
        self._credentials_port = credentials_port

    async def execute(self) -> AvailableSources:
        scrape_config = self._config_port.load().scrape

        virtual_enabled = scrape_config.virtual.enabled

        logged_entity_ids = {e.id for e in self._credentials_port.get_available_entities()}

        entities = []
        for native_entity in NATIVE_ENTITIES:
            setup = native_entity.id in logged_entity_ids
            entities.append(
                AvailableFinancialEntity(**asdict(native_entity), setup=setup)
            )

        return AvailableSources(
            virtual=virtual_enabled,
            entities=entities
        )
