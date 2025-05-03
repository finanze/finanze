from application.ports.config_port import ConfigPort
from domain.settings import Settings
from domain.use_cases.get_settings import GetSettings


class GetSettingsImpl(GetSettings):

    def __init__(self, config_port: ConfigPort):
        self._config_port = config_port

    def execute(self) -> Settings:
        return self._config_port.load()
