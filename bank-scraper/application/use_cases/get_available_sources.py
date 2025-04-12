from application.ports.config_port import ConfigPort
from domain.available_sources import AvailableSources
from domain.native_entities import NATIVE_ENTITIES
from domain.use_cases.get_available_sources import GetAvailableSources


class GetAvailableSourcesImpl(GetAvailableSources):

    def __init__(self, config_port: ConfigPort):
        self._config_port = config_port

    async def execute(self) -> AvailableSources:
        scrape_config = self._config_port.load()["scrape"]

        virtual_enabled = scrape_config["virtual"]["enabled"]

        enabled_entities_config = scrape_config.get("enabledEntities", [e.name for e in NATIVE_ENTITIES])

        enabled_entities = [
            entity for entity in NATIVE_ENTITIES
            if entity.name in enabled_entities_config
        ]

        return AvailableSources(
            virtual=virtual_enabled,
            entities=enabled_entities
        )
