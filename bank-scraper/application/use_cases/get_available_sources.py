from application.ports.config_port import ConfigPort
from application.ports.credentials_port import CredentialsPort
from domain.available_sources import AvailableSources
from domain.use_cases.get_available_sources import GetAvailableSources


class GetAvailableSourcesImpl(GetAvailableSources):

    def __init__(self,
                 config_port: ConfigPort,
                 credentials_port: CredentialsPort):
        self._config_port = config_port
        self._credentials_port = credentials_port

    async def execute(self) -> AvailableSources:
        scrape_config = self._config_port.load()["scrape"]

        virtual_enabled = scrape_config["virtual"]["enabled"]

        enabled_entities = self._credentials_port.get_available_entities()

        return AvailableSources(
            virtual=virtual_enabled,
            entities=enabled_entities
        )
